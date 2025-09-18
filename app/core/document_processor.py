import os
import time
import uuid
from typing import List, Dict, Any, Optional, Tuple
from io import BytesIO
import asyncio
import tempfile

from fastapi import UploadFile
from langchain_community.document_loaders import (
    PyPDFLoader,
    CSVLoader,
    TextLoader,
    UnstructuredWordDocumentLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from app.config import settings
from app.core.embeddings import embedding_manager
from app.utils.exceptions import DocumentProcessingException


class DocumentProcessor:
    """Document processor for parsing, chunking, and indexing documents"""

    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.max_chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
        )
        self.supported_types = {
            "application/pdf": self._process_pdf,
            "text/plain": self._process_text,
            "text/csv": self._process_csv,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": self._process_docx,
            "application/msword": self._process_doc
        }

    async def process_documents(
        self,
        files: List[UploadFile],
        organization_id: str,
        business_context_id: str
    ) -> Dict[str, Any]:
        """
        Process multiple documents and store in vector database

        Args:
            files: List of uploaded files
            organization_id: Organization ID
            business_context_id: Business context ID

        Returns:
            Processing results with metadata
        """
        try:
            collection_name = f"org_{organization_id}"

            # Ensure collection exists
            await embedding_manager.create_collection(collection_name)

            results = {
                "total_files": len(files),
                "processed_files": 0,
                "failed_files": 0,
                "total_chunks": 0,
                "processing_details": [],
                "collection_name": collection_name
            }

            # Process each file
            for file in files:
                try:
                    file_result = await self._process_single_file(
                        file, organization_id, business_context_id, collection_name
                    )
                    results["processed_files"] += 1
                    results["total_chunks"] += file_result["chunks_created"]
                    results["processing_details"].append(file_result)

                except Exception as e:
                    results["failed_files"] += 1
                    results["processing_details"].append({
                        "filename": file.filename,
                        "status": "failed",
                        "error": str(e),
                        "chunks_created": 0
                    })

            return results

        except Exception as e:
            raise DocumentProcessingException(f"Document processing failed: {str(e)}")

    async def _process_single_file(
        self,
        file: UploadFile,
        organization_id: str,
        business_context_id: str,
        collection_name: str
    ) -> Dict[str, Any]:
        """Process a single file"""
        start_time = time.time()

        # Validate file type
        if file.content_type not in self.supported_types:
            raise DocumentProcessingException(
                f"Unsupported file type: {file.content_type}. "
                f"Supported types: {list(self.supported_types.keys())}"
            )

        # Validate file size
        content = await file.read()
        if len(content) > settings.max_file_size:
            raise DocumentProcessingException(
                f"File too large: {len(content)} bytes. Max size: {settings.max_file_size} bytes"
            )

        # Reset file position
        await file.seek(0)

        # Process file based on type
        processor = self.supported_types[file.content_type]
        documents = await processor(file, content)

        # Add metadata to documents
        for doc in documents:
            doc.metadata.update({
                "organization_id": organization_id,
                "business_context_id": business_context_id,
                "source_file": file.filename,
                "content_type": file.content_type,
                "file_size": len(content),
                "processed_at": int(time.time())
            })

        # Split documents into chunks
        chunks = self.text_splitter.split_documents(documents)

        # Prepare documents for vector store
        vector_documents = []
        for i, chunk in enumerate(chunks):
            vector_documents.append({
                "id": f"{uuid.uuid4()}",
                "content": chunk.page_content,
                "metadata": {
                    **chunk.metadata,
                    "chunk_index": i,
                    "chunk_id": f"{file.filename}_{i}"
                }
            })

        # Add to vector store
        added_count = await embedding_manager.add_documents(
            collection_name, vector_documents
        )

        processing_time = time.time() - start_time

        return {
            "filename": file.filename,
            "content_type": file.content_type,
            "file_size": len(content),
            "status": "success",
            "chunks_created": added_count,
            "processing_time": processing_time,
            "document_count": len(documents)
        }

    async def _process_pdf(self, file: UploadFile, content: bytes) -> List[Document]:
        """Process PDF file"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(content)
            temp_file.flush()

            try:
                loader = PyPDFLoader(temp_file.name)
                documents = loader.load()
                return documents
            finally:
                os.unlink(temp_file.name)

    async def _process_text(self, file: UploadFile, content: bytes) -> List[Document]:
        """Process text file"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="wb") as temp_file:
            temp_file.write(content)
            temp_file.flush()

            try:
                loader = TextLoader(temp_file.name, encoding="utf-8")
                documents = loader.load()
                return documents
            finally:
                os.unlink(temp_file.name)

    async def _process_csv(self, file: UploadFile, content: bytes) -> List[Document]:
        """Process CSV file"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="wb") as temp_file:
            temp_file.write(content)
            temp_file.flush()

            try:
                loader = CSVLoader(temp_file.name)
                documents = loader.load()
                return documents
            finally:
                os.unlink(temp_file.name)

    async def _process_docx(self, file: UploadFile, content: bytes) -> List[Document]:
        """Process DOCX file"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_file:
            temp_file.write(content)
            temp_file.flush()

            try:
                loader = UnstructuredWordDocumentLoader(temp_file.name)
                documents = loader.load()
                return documents
            finally:
                os.unlink(temp_file.name)

    async def _process_doc(self, file: UploadFile, content: bytes) -> List[Document]:
        """Process DOC file"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".doc") as temp_file:
            temp_file.write(content)
            temp_file.flush()

            try:
                loader = UnstructuredWordDocumentLoader(temp_file.name)
                documents = loader.load()
                return documents
            finally:
                os.unlink(temp_file.name)

    async def search_documents(
        self,
        organization_id: str,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search documents for an organization"""
        collection_name = f"org_{organization_id}"

        try:
            results = await embedding_manager.search_similar(
                collection_name=collection_name,
                query=query,
                limit=limit,
                score_threshold=score_threshold,
                filter_conditions={"organization_id": organization_id}
            )
            return results
        except Exception as e:
            raise DocumentProcessingException(f"Document search failed: {str(e)}")

    async def get_document_stats(self, organization_id: str) -> Dict[str, Any]:
        """Get document statistics for an organization"""
        collection_name = f"org_{organization_id}"

        try:
            collection_info = await embedding_manager.get_collection_info(collection_name)

            # Additional stats could be calculated here
            # For now, return basic collection info
            return {
                "collection_name": collection_name,
                "total_chunks": collection_info["points_count"],
                "indexed_vectors": collection_info["indexed_vectors_count"],
                "collection_status": collection_info["status"]
            }
        except Exception as e:
            raise DocumentProcessingException(f"Failed to get document stats: {str(e)}")

    async def delete_organization_documents(self, organization_id: str) -> bool:
        """Delete all documents for an organization"""
        collection_name = f"org_{organization_id}"

        try:
            await embedding_manager.delete_collection(collection_name)
            return True
        except Exception as e:
            raise DocumentProcessingException(f"Failed to delete organization documents: {str(e)}")

    async def update_document_chunk(
        self,
        organization_id: str,
        chunk_id: str,
        new_content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update a specific document chunk"""
        collection_name = f"org_{organization_id}"

        try:
            updated_metadata = metadata or {}
            updated_metadata["organization_id"] = organization_id
            updated_metadata["updated_at"] = int(time.time())

            return await embedding_manager.update_document(
                collection_name=collection_name,
                document_id=chunk_id,
                content=new_content,
                metadata=updated_metadata
            )
        except Exception as e:
            raise DocumentProcessingException(f"Failed to update document chunk: {str(e)}")

    def get_supported_file_types(self) -> List[str]:
        """Get list of supported file types"""
        return list(self.supported_types.keys())

    async def validate_files(self, files: List[UploadFile]) -> List[Dict[str, Any]]:
        """Validate uploaded files before processing"""
        validation_results = []

        for file in files:
            result = {
                "filename": file.filename,
                "content_type": file.content_type,
                "valid": True,
                "errors": []
            }

            # Check file type
            if file.content_type not in self.supported_types:
                result["valid"] = False
                result["errors"].append(f"Unsupported file type: {file.content_type}")

            # Check file size
            content = await file.read()
            await file.seek(0)  # Reset position

            if len(content) > settings.max_file_size:
                result["valid"] = False
                result["errors"].append(
                    f"File too large: {len(content)} bytes. Max: {settings.max_file_size} bytes"
                )

            result["file_size"] = len(content)
            validation_results.append(result)

        return validation_results


# Global document processor instance
document_processor = DocumentProcessor()