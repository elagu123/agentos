"""
Frontend Performance Optimizer for AgentOS
Asset optimization, caching strategies and performance monitoring
"""

from typing import Dict, List, Any, Optional, Union
import os
import json
import hashlib
import gzip
import mimetypes
from pathlib import Path
from datetime import datetime, timedelta
import time
import logging
from dataclasses import dataclass

from fastapi import Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import aiofiles

logger = logging.getLogger(__name__)

@dataclass
class AssetInfo:
    path: str
    size: int
    compressed_size: int
    hash: str
    mime_type: str
    last_modified: datetime
    cache_control: str

class AssetOptimizer:
    def __init__(self, static_dir: str = "static", cache_dir: str = "cache"):
        self.static_dir = Path(static_dir)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        # Asset cache en memoria
        self.asset_cache: Dict[str, AssetInfo] = {}

        # Configuración de compresión
        self.compression_config = {
            "level": 6,  # Nivel de compresión gzip
            "min_size": 1024,  # Tamaño mínimo para comprimir (1KB)
            "extensions": {".js", ".css", ".html", ".json", ".svg", ".txt", ".xml"}
        }

        # Cache headers por tipo de archivo
        self.cache_headers = {
            ".js": "public, max-age=31536000, immutable",  # 1 año para JS
            ".css": "public, max-age=31536000, immutable",  # 1 año para CSS
            ".png": "public, max-age=2592000",  # 30 días para imágenes
            ".jpg": "public, max-age=2592000",
            ".jpeg": "public, max-age=2592000",
            ".gif": "public, max-age=2592000",
            ".svg": "public, max-age=2592000",
            ".ico": "public, max-age=604800",  # 1 semana para favicons
            ".woff": "public, max-age=31536000",  # 1 año para fonts
            ".woff2": "public, max-age=31536000",
            ".ttf": "public, max-age=31536000",
            ".eot": "public, max-age=31536000",
            ".html": "public, max-age=0, must-revalidate",  # No cache para HTML
            ".json": "public, max-age=3600",  # 1 hora para JSON
        }

    async def initialize(self):
        """Inicializar optimizador y procesar assets"""
        await self._scan_and_process_assets()
        logger.info(f"Asset optimizer initialized with {len(self.asset_cache)} assets")

    async def _scan_and_process_assets(self):
        """Escanear y procesar todos los assets estáticos"""
        if not self.static_dir.exists():
            logger.warning(f"Static directory {self.static_dir} does not exist")
            return

        for file_path in self.static_dir.rglob("*"):
            if file_path.is_file():
                await self._process_asset(file_path)

    async def _process_asset(self, file_path: Path):
        """Procesar un asset individual"""
        try:
            relative_path = str(file_path.relative_to(self.static_dir))

            # Obtener información del archivo
            stat = file_path.stat()
            file_size = stat.st_size
            last_modified = datetime.fromtimestamp(stat.st_mtime)

            # Calcular hash del contenido
            file_hash = await self._calculate_file_hash(file_path)

            # Determinar tipo MIME
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if not mime_type:
                mime_type = "application/octet-stream"

            # Comprimir si es necesario
            compressed_size = file_size
            if self._should_compress(file_path, file_size):
                compressed_path = await self._compress_asset(file_path, file_hash)
                if compressed_path:
                    compressed_size = compressed_path.stat().st_size

            # Determinar cache control
            cache_control = self._get_cache_control(file_path.suffix)

            # Crear AssetInfo
            asset_info = AssetInfo(
                path=relative_path,
                size=file_size,
                compressed_size=compressed_size,
                hash=file_hash,
                mime_type=mime_type,
                last_modified=last_modified,
                cache_control=cache_control
            )

            self.asset_cache[relative_path] = asset_info

        except Exception as e:
            logger.error(f"Error processing asset {file_path}: {str(e)}")

    async def _calculate_file_hash(self, file_path: Path) -> str:
        """Calcular hash SHA256 del archivo"""
        hash_sha256 = hashlib.sha256()

        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                hash_sha256.update(chunk)

        return hash_sha256.hexdigest()[:16]  # Primeros 16 caracteres

    def _should_compress(self, file_path: Path, file_size: int) -> bool:
        """Determinar si un archivo debe ser comprimido"""
        # No comprimir archivos pequeños
        if file_size < self.compression_config["min_size"]:
            return False

        # Solo comprimir extensiones específicas
        if file_path.suffix.lower() not in self.compression_config["extensions"]:
            return False

        return True

    async def _compress_asset(self, file_path: Path, file_hash: str) -> Optional[Path]:
        """Comprimir un asset y guardarlo en cache"""
        try:
            compressed_path = self.cache_dir / f"{file_hash}.gz"

            # Si ya existe, no volver a comprimir
            if compressed_path.exists():
                return compressed_path

            async with aiofiles.open(file_path, 'rb') as input_file:
                content = await input_file.read()

            # Comprimir contenido
            compressed_content = gzip.compress(
                content,
                compresslevel=self.compression_config["level"]
            )

            async with aiofiles.open(compressed_path, 'wb') as output_file:
                await output_file.write(compressed_content)

            return compressed_path

        except Exception as e:
            logger.error(f"Error compressing {file_path}: {str(e)}")
            return None

    def _get_cache_control(self, file_extension: str) -> str:
        """Obtener cache control header para extensión"""
        return self.cache_headers.get(
            file_extension.lower(),
            "public, max-age=3600"  # Default: 1 hora
        )

    async def serve_optimized_asset(self, request: Request, file_path: str) -> Response:
        """Servir asset optimizado con headers apropiados"""

        # Normalizar path
        file_path = file_path.lstrip("/")

        # Verificar si existe en cache
        asset_info = self.asset_cache.get(file_path)
        if not asset_info:
            return Response(status_code=404, content="Asset not found")

        full_path = self.static_dir / file_path
        if not full_path.exists():
            return Response(status_code=404, content="Asset not found")

        # Headers de respuesta
        headers = {
            "Cache-Control": asset_info.cache_control,
            "ETag": f'"{asset_info.hash}"',
            "Last-Modified": asset_info.last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")
        }

        # Verificar If-None-Match (ETag)
        if_none_match = request.headers.get("If-None-Match")
        if if_none_match and if_none_match.strip('"') == asset_info.hash:
            return Response(status_code=304, headers=headers)

        # Verificar If-Modified-Since
        if_modified_since = request.headers.get("If-Modified-Since")
        if if_modified_since:
            try:
                client_time = datetime.strptime(if_modified_since, "%a, %d %b %Y %H:%M:%S GMT")
                if asset_info.last_modified <= client_time:
                    return Response(status_code=304, headers=headers)
            except ValueError:
                pass

        # Verificar soporte de compresión
        accept_encoding = request.headers.get("Accept-Encoding", "")
        use_compression = "gzip" in accept_encoding and self._should_compress(full_path, asset_info.size)

        if use_compression:
            compressed_path = self.cache_dir / f"{asset_info.hash}.gz"
            if compressed_path.exists():
                headers["Content-Encoding"] = "gzip"
                headers["Content-Length"] = str(asset_info.compressed_size)
                headers["Vary"] = "Accept-Encoding"

                return FileResponse(
                    compressed_path,
                    media_type=asset_info.mime_type,
                    headers=headers
                )

        # Servir archivo sin comprimir
        headers["Content-Length"] = str(asset_info.size)

        return FileResponse(
            full_path,
            media_type=asset_info.mime_type,
            headers=headers
        )

    def get_asset_url(self, file_path: str, version: bool = True) -> str:
        """Generar URL de asset con versionado opcional"""
        file_path = file_path.lstrip("/")

        if version and file_path in self.asset_cache:
            asset_info = self.asset_cache[file_path]
            return f"/static/{file_path}?v={asset_info.hash}"

        return f"/static/{file_path}"

    def get_critical_css_paths(self, page: str) -> List[str]:
        """Obtener paths de CSS crítico para una página"""
        # Mapeo de páginas a CSS crítico
        critical_css_map = {
            "dashboard": ["css/dashboard.css", "css/components.css"],
            "workflow": ["css/workflow.css", "css/editor.css"],
            "marketplace": ["css/marketplace.css", "css/cards.css"],
            "agents": ["css/agents.css", "css/forms.css"],
            "analytics": ["css/analytics.css", "css/charts.css"]
        }

        return critical_css_map.get(page, ["css/main.css"])

    async def preload_critical_assets(self, page: str) -> List[str]:
        """Generar tags de preload para assets críticos"""
        preload_tags = []

        # CSS crítico
        critical_css = self.get_critical_css_paths(page)
        for css_path in critical_css:
            if css_path in self.asset_cache:
                url = self.get_asset_url(css_path)
                preload_tags.append(f'<link rel="preload" href="{url}" as="style">')

        # JavaScript crítico
        critical_js = ["js/app.js", "js/utils.js"]
        for js_path in critical_js:
            if js_path in self.asset_cache:
                url = self.get_asset_url(js_path)
                preload_tags.append(f'<link rel="preload" href="{url}" as="script">')

        # Fonts críticas
        critical_fonts = ["fonts/inter.woff2", "fonts/icons.woff2"]
        for font_path in critical_fonts:
            if font_path in self.asset_cache:
                url = self.get_asset_url(font_path)
                preload_tags.append(f'<link rel="preload" href="{url}" as="font" type="font/woff2" crossorigin>')

        return preload_tags

    def generate_service_worker_cache_list(self) -> Dict[str, Any]:
        """Generar lista de assets para Service Worker"""
        cache_list = {
            "version": int(time.time()),
            "assets": {
                "critical": [],  # Assets que deben cachearse inmediatamente
                "optional": [],  # Assets que pueden cachearse bajo demanda
                "exclude": []    # Assets que no deben cachearse
            }
        }

        for path, asset_info in self.asset_cache.items():
            url = self.get_asset_url(path)

            # Clasificar assets
            if path.startswith(("css/", "js/")) and asset_info.size < 100 * 1024:  # < 100KB
                cache_list["assets"]["critical"].append(url)
            elif path.startswith(("images/", "fonts/")):
                cache_list["assets"]["optional"].append(url)
            elif asset_info.size > 1024 * 1024:  # > 1MB
                cache_list["assets"]["exclude"].append(url)
            else:
                cache_list["assets"]["optional"].append(url)

        return cache_list

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Obtener métricas de performance de assets"""
        total_assets = len(self.asset_cache)
        total_size = sum(asset.size for asset in self.asset_cache.values())
        total_compressed = sum(asset.compressed_size for asset in self.asset_cache.values())

        # Agrupar por tipo
        by_type = {}
        for asset_info in self.asset_cache.values():
            ext = Path(asset_info.path).suffix.lower()
            if ext not in by_type:
                by_type[ext] = {"count": 0, "size": 0, "compressed_size": 0}

            by_type[ext]["count"] += 1
            by_type[ext]["size"] += asset_info.size
            by_type[ext]["compressed_size"] += asset_info.compressed_size

        compression_ratio = (total_compressed / total_size * 100) if total_size > 0 else 0

        return {
            "total_assets": total_assets,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "total_compressed_bytes": total_compressed,
            "total_compressed_mb": round(total_compressed / (1024 * 1024), 2),
            "compression_ratio": round(compression_ratio, 1),
            "savings_bytes": total_size - total_compressed,
            "savings_percentage": round(100 - compression_ratio, 1),
            "by_type": by_type,
            "cache_hit_recommendations": self._get_cache_recommendations()
        }

    def _get_cache_recommendations(self) -> List[str]:
        """Generar recomendaciones de optimización"""
        recommendations = []

        large_assets = [
            asset for asset in self.asset_cache.values()
            if asset.size > 500 * 1024  # > 500KB
        ]

        if large_assets:
            recommendations.append(f"Consider optimizing {len(large_assets)} large assets (>500KB)")

        uncompressed = [
            asset for asset in self.asset_cache.values()
            if asset.size == asset.compressed_size and asset.size > 10 * 1024
        ]

        if uncompressed:
            recommendations.append(f"Consider enabling compression for {len(uncompressed)} assets")

        short_cache = [
            asset for asset in self.asset_cache.values()
            if "max-age=3600" in asset.cache_control
        ]

        if short_cache:
            recommendations.append(f"Consider longer cache times for {len(short_cache)} static assets")

        return recommendations

class PerformanceMiddleware:
    """Middleware para optimización de performance"""

    def __init__(self):
        self.request_times = []
        self.max_stored_times = 1000

    async def __call__(self, request: Request, call_next):
        start_time = time.time()

        # Headers de performance
        response = await call_next(request)

        # Calcular tiempo de respuesta
        process_time = time.time() - start_time
        self.request_times.append(process_time)

        # Mantener solo las últimas 1000 requests
        if len(self.request_times) > self.max_stored_times:
            self.request_times = self.request_times[-self.max_stored_times:]

        # Headers de performance
        response.headers["X-Process-Time"] = str(round(process_time, 4))
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Headers de compresión si no están presentes
        if not response.headers.get("Vary"):
            response.headers["Vary"] = "Accept-Encoding"

        return response

    def get_performance_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de performance"""
        if not self.request_times:
            return {"message": "No requests recorded"}

        times = self.request_times

        return {
            "total_requests": len(times),
            "avg_response_time": round(sum(times) / len(times), 4),
            "min_response_time": round(min(times), 4),
            "max_response_time": round(max(times), 4),
            "p95_response_time": round(sorted(times)[int(len(times) * 0.95)], 4),
            "p99_response_time": round(sorted(times)[int(len(times) * 0.99)], 4),
            "slow_requests": len([t for t in times if t > 1.0]),  # > 1 segundo
            "fast_requests": len([t for t in times if t < 0.1])   # < 100ms
        }

# Instancias globales
asset_optimizer = AssetOptimizer()
performance_middleware = PerformanceMiddleware()

# Utilidades de templating
class TemplateOptimizer:
    """Optimizador para templates HTML"""

    @staticmethod
    def inject_performance_headers(html: str, page: str) -> str:
        """Inyectar headers de performance en HTML"""

        # DNS prefetch para servicios externos
        dns_prefetch = [
            '<link rel="dns-prefetch" href="//fonts.googleapis.com">',
            '<link rel="dns-prefetch" href="//api.openai.com">',
            '<link rel="dns-prefetch" href="//cdn.jsdelivr.net">'
        ]

        # Preconnect para recursos críticos
        preconnect = [
            '<link rel="preconnect" href="https://fonts.googleapis.com" crossorigin>',
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        ]

        # Insertar en head
        head_end = "</head>"
        if head_end in html:
            performance_tags = "\n".join(dns_prefetch + preconnect)
            html = html.replace(head_end, f"{performance_tags}\n{head_end}")

        return html

    @staticmethod
    def minify_html(html: str) -> str:
        """Minificar HTML básico"""
        import re

        # Remover comentarios HTML
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

        # Normalizar espacios en blanco
        html = re.sub(r'\s+', ' ', html)

        # Remover espacios alrededor de tags
        html = re.sub(r'>\s+<', '><', html)

        return html.strip()

# Configuración recomendada
FRONTEND_OPTIMIZATION_CONFIG = {
    "compression": {
        "enabled": True,
        "level": 6,
        "min_size": 1024
    },
    "caching": {
        "static_assets": "31536000",  # 1 año
        "api_responses": "300",       # 5 minutos
        "html_pages": "0"             # No cache
    },
    "preload": {
        "critical_css": True,
        "critical_js": True,
        "fonts": True
    },
    "service_worker": {
        "enabled": True,
        "cache_strategy": "stale-while-revalidate"
    }
}