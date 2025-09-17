"""
Embedding Optimizer for AgentOS
High-performance batch processing and caching for embeddings
"""

from typing import List, Dict, Tuple, Optional, Any
import numpy as np
import asyncio
from datetime import datetime, timedelta
import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor
import time

from .cache_manager import cache_manager

logger = logging.getLogger(__name__)

class EmbeddingOptimizer:
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model = model
        self.batch_size = 100  # OpenAI limit
        self.max_concurrent_batches = 5
        self.cache = {}  # Cache local en memoria para sesión
        self.stats = {
            "total_processed": 0,
            "cache_hits": 0,
            "api_calls": 0,
            "tokens_used": 0,
            "total_cost": 0.0,
            "batch_processing_time": 0.0,
            "average_embedding_time": 0.0
        }

        # Precios por modelo (actualizar según OpenAI)
        self.pricing = {
            "text-embedding-3-small": 0.00002,  # per 1K tokens
            "text-embedding-3-large": 0.00013,
            "text-embedding-ada-002": 0.0001
        }

    def _get_cache_key(self, text: str) -> str:
        """Generar key para cache de embeddings"""
        return hashlib.md5(f"{self.model}:{text}".encode()).hexdigest()

    async def get_embeddings(
        self,
        texts: List[str],
        use_cache: bool = True,
        use_redis_cache: bool = True
    ) -> List[List[float]]:
        """
        Obtener embeddings con batch processing y caching multinivel

        Args:
            texts: Lista de textos para procesar
            use_cache: Usar cache local en memoria
            use_redis_cache: Usar cache Redis persistente

        Returns:
            Lista de embeddings
        """
        start_time = time.time()
        results = [None] * len(texts)
        texts_to_process = []
        indices_to_process = []

        # Layer 1: Check local cache
        if use_cache:
            for i, text in enumerate(texts):
                cache_key = self._get_cache_key(text)
                if cache_key in self.cache:
                    results[i] = self.cache[cache_key]
                    self.stats["cache_hits"] += 1
                else:
                    texts_to_process.append((i, text))

        else:
            texts_to_process = [(i, text) for i, text in enumerate(texts)]

        # Layer 2: Check Redis cache
        if use_redis_cache and texts_to_process:
            redis_results = await self._check_redis_cache([item[1] for item in texts_to_process])

            remaining_texts = []
            for j, (original_index, text) in enumerate(texts_to_process):
                if redis_results[j] is not None:
                    results[original_index] = redis_results[j]
                    # Store in local cache too
                    if use_cache:
                        cache_key = self._get_cache_key(text)
                        self.cache[cache_key] = redis_results[j]
                    self.stats["cache_hits"] += 1
                else:
                    remaining_texts.append((original_index, text))

            texts_to_process = remaining_texts

        # Layer 3: Process uncached texts
        if texts_to_process:
            just_texts = [item[1] for item in texts_to_process]
            indices_map = {i: item[0] for i, item in enumerate(texts_to_process)}

            embeddings = await self._process_batches(just_texts)

            # Store results and cache
            for i, embedding in enumerate(embeddings):
                original_index = indices_map[i]
                results[original_index] = embedding

                text = just_texts[i]

                # Store in local cache
                if use_cache:
                    cache_key = self._get_cache_key(text)
                    self.cache[cache_key] = embedding

                # Store in Redis cache
                if use_redis_cache:
                    await self._store_redis_cache(text, embedding)

        processing_time = time.time() - start_time
        self.stats["batch_processing_time"] += processing_time
        self.stats["total_processed"] += len(texts)

        if self.stats["total_processed"] > 0:
            self.stats["average_embedding_time"] = self.stats["batch_processing_time"] / self.stats["total_processed"]

        return results

    async def _check_redis_cache(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Check Redis cache para múltiples textos"""
        results = []

        for text in texts:
            cache_key = f"embedding:{self.model}:{self._get_cache_key(text)}"
            cached_embedding = await cache_manager.get(cache_key)

            if cached_embedding and isinstance(cached_embedding, list):
                results.append(cached_embedding)
            else:
                results.append(None)

        return results

    async def _store_redis_cache(self, text: str, embedding: List[float]):
        """Store embedding en Redis cache"""
        cache_key = f"embedding:{self.model}:{self._get_cache_key(text)}"
        # Cache embeddings por 24 horas
        await cache_manager.set(cache_key, embedding, ttl=86400)

    async def _process_batches(self, texts: List[str]) -> List[List[float]]:
        """Procesar textos en batches optimizados"""
        all_embeddings = []

        # Dividir en batches
        batches = [
            texts[i:i+self.batch_size]
            for i in range(0, len(texts), self.batch_size)
        ]

        # Procesar batches con limitación de concurrencia
        semaphore = asyncio.Semaphore(self.max_concurrent_batches)

        async def process_batch(batch: List[str]) -> List[List[float]]:
            async with semaphore:
                return await self._call_openai_api(batch)

        # Ejecutar todos los batches
        tasks = [process_batch(batch) for batch in batches]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Procesar resultados y manejar errores
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                logger.error(f"Batch {i} failed: {str(result)}")
                # Reintentar batch individual
                try:
                    retry_result = await self._call_openai_api(batches[i])
                    all_embeddings.extend(retry_result)
                except Exception as e:
                    logger.error(f"Retry failed for batch {i}: {str(e)}")
                    # Crear embeddings dummy como fallback
                    dummy_embeddings = [[0.0] * 1536 for _ in batches[i]]
                    all_embeddings.extend(dummy_embeddings)
            else:
                all_embeddings.extend(result)

        return all_embeddings

    async def _call_openai_api(self, texts: List[str]) -> List[List[float]]:
        """Llamar a la API de OpenAI con manejo de errores y retries"""
        import httpx
        from tenacity import retry, stop_after_attempt, wait_exponential

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10)
        )
        async def make_request():
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "input": texts,
                        "encoding_format": "float"
                    }
                )

                if response.status_code != 200:
                    raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")

                return response.json()

        try:
            response_data = await make_request()

            # Actualizar estadísticas
            self.stats["api_calls"] += 1
            usage = response_data.get("usage", {})
            tokens_used = usage.get("total_tokens", 0)
            self.stats["tokens_used"] += tokens_used

            # Calcular costo
            cost_per_token = self.pricing.get(self.model, 0.0001) / 1000
            batch_cost = tokens_used * cost_per_token
            self.stats["total_cost"] += batch_cost

            # Extraer embeddings
            embeddings = [item["embedding"] for item in response_data["data"]]

            logger.debug(f"Processed batch of {len(texts)} texts, used {tokens_used} tokens, cost ${batch_cost:.6f}")

            return embeddings

        except Exception as e:
            logger.error(f"OpenAI API call failed: {str(e)}")
            raise

    async def get_embeddings_with_metadata(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Procesar documentos con metadata completa

        Args:
            documents: Lista de docs con formato {"text": str, "id": str, "metadata": dict}

        Returns:
            Lista de documentos con embeddings añadidos
        """
        start_time = time.time()

        texts = [doc["text"] for doc in documents]
        embeddings = await self.get_embeddings(texts)

        results = []
        for doc, embedding in zip(documents, embeddings):
            enhanced_doc = {
                **doc,
                "embedding": embedding,
                "embedding_model": self.model,
                "embedding_dimension": len(embedding),
                "processed_at": datetime.utcnow().isoformat(),
                "processing_time_ms": round((time.time() - start_time) * 1000, 2)
            }
            results.append(enhanced_doc)

        return results

    def estimate_cost(self, num_texts: int, avg_tokens_per_text: int = 50) -> Dict[str, Any]:
        """Estimar costo de procesamiento"""
        total_tokens = num_texts * avg_tokens_per_text
        cost_per_1k_tokens = self.pricing.get(self.model, 0.0001)
        estimated_cost = (total_tokens / 1000) * cost_per_1k_tokens

        return {
            "num_texts": num_texts,
            "estimated_tokens": total_tokens,
            "estimated_cost_usd": round(estimated_cost, 6),
            "cost_per_1k_tokens": cost_per_1k_tokens,
            "model": self.model,
            "batch_count": (num_texts + self.batch_size - 1) // self.batch_size
        }

    async def optimize_batch_size(self, sample_texts: List[str]) -> int:
        """Determinar tamaño de batch óptimo basado en performance"""
        if len(sample_texts) < 10:
            return self.batch_size

        # Test diferentes tamaños de batch
        test_sizes = [25, 50, 75, 100]
        performance_results = {}

        for size in test_sizes:
            if size > len(sample_texts):
                continue

            test_texts = sample_texts[:size]
            start_time = time.time()

            try:
                await self._call_openai_api(test_texts)
                duration = time.time() - start_time
                texts_per_second = size / duration

                performance_results[size] = {
                    "duration": duration,
                    "texts_per_second": texts_per_second,
                    "efficiency": texts_per_second / size  # Normalizado por tamaño
                }

                logger.debug(f"Batch size {size}: {texts_per_second:.2f} texts/sec")

            except Exception as e:
                logger.warning(f"Batch size {size} test failed: {str(e)}")
                performance_results[size] = {"duration": float('inf'), "texts_per_second": 0, "efficiency": 0}

        # Encontrar el tamaño más eficiente
        if performance_results:
            optimal_size = max(performance_results.keys(), key=lambda x: performance_results[x]["efficiency"])
            logger.info(f"Optimal batch size determined: {optimal_size}")
            return optimal_size

        return self.batch_size

    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas detalladas de uso"""
        cache_rate = (
            self.stats["cache_hits"] / self.stats["total_processed"] * 100
            if self.stats["total_processed"] > 0 else 0
        )

        return {
            **self.stats,
            "cache_rate": f"{cache_rate:.1f}%",
            "local_cache_size": len(self.cache),
            "memory_usage_mb": self._estimate_memory_usage(),
            "cost_per_embedding": (
                self.stats["total_cost"] / self.stats["total_processed"]
                if self.stats["total_processed"] > 0 else 0
            ),
            "api_efficiency": (
                self.stats["total_processed"] / self.stats["api_calls"]
                if self.stats["api_calls"] > 0 else 0
            )
        }

    def _estimate_memory_usage(self) -> float:
        """Estimar uso de memoria del cache local"""
        if not self.cache:
            return 0

        # Estimación: cada embedding es ~1536 floats * 4 bytes = ~6KB
        # Más overhead de Python dict
        embedding_size_kb = 1536 * 4 / 1024  # KB por embedding
        overhead_kb = len(self.cache) * 0.5  # Overhead de dict

        total_kb = len(self.cache) * embedding_size_kb + overhead_kb
        return round(total_kb / 1024, 2)  # MB

    def clear_local_cache(self):
        """Limpiar cache local en memoria"""
        cleared_count = len(self.cache)
        self.cache.clear()
        logger.info(f"Cleared {cleared_count} embeddings from local cache")
        return cleared_count

    async def clear_redis_cache(self) -> int:
        """Limpiar cache Redis de embeddings"""
        pattern = f"embedding:{self.model}:*"
        cleared_count = await cache_manager.delete_pattern(pattern)
        logger.info(f"Cleared {cleared_count} embeddings from Redis cache")
        return cleared_count

    async def precompute_embeddings(
        self,
        text_batches: List[List[str]],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Precomputar embeddings para lotes de texto

        Args:
            text_batches: Lista de lotes de texto
            progress_callback: Función callback para reportar progreso

        Returns:
            Estadísticas de precomputación
        """
        start_time = time.time()
        total_texts = sum(len(batch) for batch in text_batches)
        processed_texts = 0

        logger.info(f"Starting precomputation of {total_texts} embeddings in {len(text_batches)} batches")

        for i, batch in enumerate(text_batches):
            try:
                await self.get_embeddings(batch, use_cache=True, use_redis_cache=True)
                processed_texts += len(batch)

                if progress_callback:
                    progress = (processed_texts / total_texts) * 100
                    progress_callback(progress, processed_texts, total_texts)

                logger.debug(f"Completed batch {i+1}/{len(text_batches)}")

            except Exception as e:
                logger.error(f"Failed to precompute batch {i}: {str(e)}")

        total_time = time.time() - start_time

        return {
            "total_texts": total_texts,
            "processed_texts": processed_texts,
            "success_rate": (processed_texts / total_texts) * 100 if total_texts > 0 else 0,
            "total_time_seconds": total_time,
            "texts_per_second": processed_texts / total_time if total_time > 0 else 0,
            "final_stats": self.get_stats()
        }

# Instancia global optimizada
embedding_optimizer = None

def get_embedding_optimizer(api_key: str = None, model: str = "text-embedding-3-small") -> EmbeddingOptimizer:
    """Obtener instancia global del optimizador"""
    global embedding_optimizer

    if embedding_optimizer is None or (api_key and embedding_optimizer.api_key != api_key):
        embedding_optimizer = EmbeddingOptimizer(api_key, model)

    return embedding_optimizer