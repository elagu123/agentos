from typing import List, Dict, Any, Optional, Tuple
import asyncio
import time
from abc import ABC, abstractmethod

import numpy as np
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchRequest
)

from app.config import settings
from app.utils.exceptions import VectorStoreException, LLMException
from app.core.cache import cache_manager, cache_rag_results


class BaseEmbeddingProvider(ABC):
    """Base class for embedding providers"""

    @abstractmethod
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Get embedding dimension"""
        pass


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI embedding provider"""

    def __init__(self, api_key: str, model: str = "text-embedding-ada-002"):
        self.api_key = api_key
        self.model = model
        self.embedding_client = OpenAIEmbeddings(
            openai_api_key=api_key,
            model=model
        )

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI"""
        try:
            embeddings = await self.embedding_client.aembed_documents(texts)
            return embeddings
        except Exception as e:
            raise LLMException(f"OpenAI embedding generation failed: {str(e)}")

    def get_dimension(self) -> int:
        """Get embedding dimension for text-embedding-ada-002"""
        if self.model == "text-embedding-ada-002":
            return 1536
        elif self.model == "text-embedding-3-small":
            return 1536
        elif self.model == "text-embedding-3-large":
            return 3072
        else:
            return 1536  # Default


class EmbeddingManager:
    """Manager for generating and storing embeddings"""

    def __init__(self):
        self.provider = self._initialize_provider()
        self.qdrant_client = self._initialize_qdrant()

    def _initialize_provider(self) -> BaseEmbeddingProvider:
        """Initialize embedding provider"""
        if not settings.openai_api_key:
            raise VectorStoreException("OpenAI API key required for embeddings")

        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.embedding_model
        )

    def _initialize_qdrant(self) -> QdrantClient:
        """Initialize Qdrant client"""
        try:
            client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                api_key=settings.qdrant_api_key
            )
            return client
        except Exception as e:
            raise VectorStoreException(f"Failed to connect to Qdrant: {str(e)}")

    async def create_collection(
        self,
        collection_name: str,
        dimension: Optional[int] = None
    ) -> bool:
        """Create a new Qdrant collection"""
        try:
            dimension = dimension or self.provider.get_dimension()

            # Check if collection exists
            collections = self.qdrant_client.get_collections()
            if any(col.name == collection_name for col in collections.collections):
                return True

            # Create collection
            self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=dimension,
                    distance=Distance.COSINE
                )
            )
            return True
        except Exception as e:
            raise VectorStoreException(f"Failed to create collection {collection_name}: {str(e)}")

    async def delete_collection(self, collection_name: str) -> bool:
        """Delete a Qdrant collection"""
        try:
            self.qdrant_client.delete_collection(collection_name)
            return True
        except Exception as e:
            raise VectorStoreException(f"Failed to delete collection {collection_name}: {str(e)}")

    async def add_documents(
        self,
        collection_name: str,
        documents: List[Dict[str, Any]],
        batch_size: int = 100
    ) -> int:
        """
        Add documents to collection with embeddings

        Args:
            collection_name: Name of the collection
            documents: List of documents with 'content' and 'metadata' fields
            batch_size: Number of documents to process in each batch

        Returns:
            Number of documents added
        """
        try:
            total_added = 0

            # Process in batches
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]

                # Extract content for embedding
                texts = [doc["content"] for doc in batch]

                # Generate embeddings
                embeddings = await self.provider.generate_embeddings(texts)

                # Create points for Qdrant
                points = []
                for j, (doc, embedding) in enumerate(zip(batch, embeddings)):
                    point_id = doc.get("id") or f"{int(time.time())}_{i}_{j}"

                    # Prepare metadata
                    metadata = doc.get("metadata", {})
                    metadata["content"] = doc["content"]
                    metadata["indexed_at"] = int(time.time())

                    points.append(
                        PointStruct(
                            id=point_id,
                            vector=embedding,
                            payload=metadata
                        )
                    )

                # Upload to Qdrant
                self.qdrant_client.upsert(
                    collection_name=collection_name,
                    points=points
                )

                total_added += len(batch)

            return total_added
        except Exception as e:
            raise VectorStoreException(f"Failed to add documents to {collection_name}: {str(e)}")

    async def search_similar(
        self,
        collection_name: str,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.7,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents with caching

        Args:
            collection_name: Name of the collection
            query: Search query
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            filter_conditions: Optional metadata filters

        Returns:
            List of similar documents with scores
        """
        # Extract org_id from collection name for cache key
        org_id = collection_name.replace("org_", "").replace("_docs", "")

        # Check cache first
        cached_results = await cache_manager.get_cached_rag(query, org_id)
        if cached_results:
            # Filter cached results based on current parameters
            filtered_results = [
                r for r in cached_results
                if r.get("score", 0) >= score_threshold
            ][:limit]
            return filtered_results

        try:
            # Generate query embedding
            query_embeddings = await self.provider.generate_embeddings([query])
            query_vector = query_embeddings[0]

            # Prepare filter
            search_filter = None
            if filter_conditions:
                conditions = []
                for key, value in filter_conditions.items():
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value)
                        )
                    )
                search_filter = Filter(must=conditions)

            # Search in Qdrant
            search_results = self.qdrant_client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=search_filter,
                with_payload=True
            )

            # Format results
            results = []
            for result in search_results:
                results.append({
                    "id": result.id,
                    "content": result.payload.get("content", ""),
                    "metadata": {k: v for k, v in result.payload.items() if k != "content"},
                    "score": result.score,
                    "source": result.payload.get("source", "business_documents"),
                    "type": "business_context"
                })

            # Cache the results for future queries
            if results:
                await cache_manager.cache_rag_search(
                    query=query,
                    org_id=org_id,
                    results=results,
                    expire_time=3600  # 1 hour cache
                )

            return results
        except Exception as e:
            raise VectorStoreException(f"Failed to search in {collection_name}: {str(e)}")

    async def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Get information about a collection"""
        try:
            collection_info = self.qdrant_client.get_collection(collection_name)

            return {
                "name": collection_name,
                "vector_size": collection_info.config.params.vectors.size,
                "distance": collection_info.config.params.vectors.distance.name,
                "points_count": collection_info.points_count,
                "indexed_vectors_count": collection_info.indexed_vectors_count,
                "status": collection_info.status.name
            }
        except Exception as e:
            raise VectorStoreException(f"Failed to get collection info for {collection_name}: {str(e)}")

    async def delete_documents(
        self,
        collection_name: str,
        document_ids: List[str]
    ) -> bool:
        """Delete specific documents from collection"""
        try:
            self.qdrant_client.delete(
                collection_name=collection_name,
                points_selector=document_ids
            )
            return True
        except Exception as e:
            raise VectorStoreException(f"Failed to delete documents from {collection_name}: {str(e)}")

    async def update_document(
        self,
        collection_name: str,
        document_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update a single document"""
        try:
            # Generate new embedding
            embeddings = await self.provider.generate_embeddings([content])
            embedding = embeddings[0]

            # Prepare metadata
            payload = metadata or {}
            payload["content"] = content
            payload["updated_at"] = int(time.time())

            # Update in Qdrant
            self.qdrant_client.upsert(
                collection_name=collection_name,
                points=[
                    PointStruct(
                        id=document_id,
                        vector=embedding,
                        payload=payload
                    )
                ]
            )
            return True
        except Exception as e:
            raise VectorStoreException(f"Failed to update document {document_id} in {collection_name}: {str(e)}")

    async def batch_search(
        self,
        collection_name: str,
        queries: List[str],
        limit: int = 5
    ) -> List[List[Dict[str, Any]]]:
        """Perform multiple searches concurrently"""
        tasks = [
            self.search_similar(collection_name, query, limit)
            for query in queries
        ]
        return await asyncio.gather(*tasks)

    def list_collections(self) -> List[str]:
        """List all available collections"""
        try:
            collections = self.qdrant_client.get_collections()
            return [col.name for col in collections.collections]
        except Exception as e:
            raise VectorStoreException(f"Failed to list collections: {str(e)}")


# Global embedding manager instance
embedding_manager = EmbeddingManager()