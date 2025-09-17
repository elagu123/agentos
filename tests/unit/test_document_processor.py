import pytest
from unittest.mock import AsyncMock, Mock, patch
from fastapi import UploadFile
from io import BytesIO
from app.core.document_processor import DocumentProcessor


class TestDocumentProcessor:
    """Test cases for DocumentProcessor"""

    @pytest.fixture
    def processor(self):
        return DocumentProcessor()

    @pytest.fixture
    def mock_upload_file(self):
        """Create a mock upload file"""
        content = b"This is test content for the document."
        file_obj = BytesIO(content)
        file = UploadFile(
            file=file_obj,
            filename="test.txt",
            headers={"content-type": "text/plain"}
        )
        file.content_type = "text/plain"
        return file

    @pytest.fixture
    def mock_pdf_file(self):
        """Create a mock PDF file"""
        content = b"%PDF-1.4 fake pdf content"
        file_obj = BytesIO(content)
        file = UploadFile(
            file=file_obj,
            filename="test.pdf",
            headers={"content-type": "application/pdf"}
        )
        file.content_type = "application/pdf"
        return file

    def test_get_supported_file_types(self, processor):
        """Test getting supported file types"""
        types = processor.get_supported_file_types()

        assert "text/plain" in types
        assert "application/pdf" in types
        assert "text/csv" in types

    @pytest.mark.asyncio
    async def test_validate_files_valid(self, processor, mock_upload_file):
        """Test file validation with valid file"""
        results = await processor.validate_files([mock_upload_file])

        assert len(results) == 1
        assert results[0]["valid"] is True
        assert results[0]["filename"] == "test.txt"
        assert len(results[0]["errors"]) == 0

    @pytest.mark.asyncio
    async def test_validate_files_invalid_type(self, processor):
        """Test file validation with invalid file type"""
        content = b"invalid content"
        file_obj = BytesIO(content)
        file = UploadFile(
            file=file_obj,
            filename="test.exe",
            headers={"content-type": "application/exe"}
        )
        file.content_type = "application/exe"

        results = await processor.validate_files([file])

        assert len(results) == 1
        assert results[0]["valid"] is False
        assert "Unsupported file type" in results[0]["errors"][0]

    @pytest.mark.asyncio
    async def test_validate_files_too_large(self, processor):
        """Test file validation with oversized file"""
        # Create a file larger than max size
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        file_obj = BytesIO(large_content)
        file = UploadFile(
            file=file_obj,
            filename="large.txt",
            headers={"content-type": "text/plain"}
        )
        file.content_type = "text/plain"

        results = await processor.validate_files([file])

        assert len(results) == 1
        assert results[0]["valid"] is False
        assert "File too large" in results[0]["errors"][0]

    @pytest.mark.asyncio
    async def test_process_text_file(self, processor, mock_upload_file):
        """Test processing a text file"""
        content = await mock_upload_file.read()

        with patch('tempfile.NamedTemporaryFile') as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = "test_file.txt"

            with patch('langchain.document_loaders.TextLoader') as mock_loader:
                from langchain.schema import Document
                mock_loader.return_value.load.return_value = [
                    Document(page_content="Test content", metadata={"source": "test.txt"})
                ]

                documents = await processor._process_text(mock_upload_file, content)

                assert len(documents) == 1
                assert documents[0].page_content == "Test content"

    @pytest.mark.asyncio
    async def test_process_pdf_file(self, processor, mock_pdf_file):
        """Test processing a PDF file"""
        content = await mock_pdf_file.read()

        with patch('tempfile.NamedTemporaryFile') as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = "test_file.pdf"

            with patch('langchain.document_loaders.PyPDFLoader') as mock_loader:
                from langchain.schema import Document
                mock_loader.return_value.load.return_value = [
                    Document(page_content="PDF content", metadata={"source": "test.pdf"})
                ]

                documents = await processor._process_pdf(mock_pdf_file, content)

                assert len(documents) == 1
                assert documents[0].page_content == "PDF content"

    @pytest.mark.asyncio
    async def test_process_documents_integration(self, processor, mock_upload_file, mock_embedding_manager):
        """Test full document processing pipeline"""
        with patch('app.core.document_processor.embedding_manager', mock_embedding_manager):
            with patch.object(processor, '_process_single_file') as mock_process:
                mock_process.return_value = {
                    "filename": "test.txt",
                    "status": "success",
                    "chunks_created": 5,
                    "processing_time": 0.5
                }

                result = await processor.process_documents(
                    files=[mock_upload_file],
                    organization_id="org123",
                    business_context_id="context123"
                )

                assert result["total_files"] == 1
                assert result["processed_files"] == 1
                assert result["failed_files"] == 0
                assert result["total_chunks"] == 5

    @pytest.mark.asyncio
    async def test_search_documents(self, processor, mock_embedding_manager):
        """Test document search functionality"""
        with patch('app.core.document_processor.embedding_manager', mock_embedding_manager):
            results = await processor.search_documents(
                organization_id="org123",
                query="test query",
                limit=5
            )

            assert len(results) == 1
            assert results[0]["content"] == "Test document"
            mock_embedding_manager.search_similar.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_document_stats(self, processor, mock_embedding_manager):
        """Test getting document statistics"""
        mock_embedding_manager.get_collection_info.return_value = {
            "points_count": 100,
            "indexed_vectors_count": 100,
            "status": "green"
        }

        with patch('app.core.document_processor.embedding_manager', mock_embedding_manager):
            stats = await processor.get_document_stats("org123")

            assert stats["total_chunks"] == 100
            assert stats["indexed_vectors"] == 100
            assert stats["collection_status"] == "green"

    @pytest.mark.asyncio
    async def test_delete_organization_documents(self, processor, mock_embedding_manager):
        """Test deleting organization documents"""
        with patch('app.core.document_processor.embedding_manager', mock_embedding_manager):
            result = await processor.delete_organization_documents("org123")

            assert result is True
            mock_embedding_manager.delete_collection.assert_called_once_with("org_org123")

    @pytest.mark.asyncio
    async def test_update_document_chunk(self, processor, mock_embedding_manager):
        """Test updating a document chunk"""
        with patch('app.core.document_processor.embedding_manager', mock_embedding_manager):
            result = await processor.update_document_chunk(
                organization_id="org123",
                chunk_id="chunk123",
                new_content="Updated content"
            )

            assert result is True
            mock_embedding_manager.update_document.assert_called_once()