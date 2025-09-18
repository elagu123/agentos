#!/bin/bash

# railway_deploy.sh - Script de deployment optimizado para AgentOS en Railway
# Basado en las mejores prácticas de Railway 2024

set -e  # Exit on any error

echo "🚀 AgentOS Railway Deployment Script"
echo "======================================"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para logging
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Verificar que estamos en el directorio correcto
if [ ! -f "railway.json" ]; then
    error "railway.json no encontrado. ¿Estás en el directorio correcto?"
fi

if [ ! -f "Dockerfile.railway" ]; then
    error "Dockerfile.railway no encontrado. Ejecuta el script de setup primero."
fi

log "Iniciando verificaciones pre-deployment..."

# 1. Verificar Railway CLI
if ! command -v railway &> /dev/null; then
    error "Railway CLI no está instalado. Instálalo con: npm install -g @railway/cli"
fi

# 2. Verificar autenticación con Railway
log "Verificando autenticación con Railway..."
if ! railway status &> /dev/null; then
    error "No estás autenticado con Railway. Ejecuta: railway login"
fi

success "✅ Autenticación con Railway verificada"

# 3. Verificar configuración del proyecto
log "Verificando configuración del proyecto..."

# Verificar que el host está configurado a 0.0.0.0
if grep -q "127.0.0.1\|localhost" app/main.py; then
    warning "⚠️  Detectado uso de localhost/127.0.0.1 en main.py"
    warning "Esto puede causar 'Application Failed to Respond' en Railway"
fi

# Verificar uso de variable PORT
if ! grep -q "PORT" app/config.py; then
    error "Variable PORT no configurada en config.py"
fi

success "✅ Configuración del proyecto verificada"

# 4. Test de build local (opcional pero recomendado)
read -p "¿Realizar test de build local? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log "Construyendo imagen Docker localmente..."

    if docker build -f Dockerfile.railway -t agentos-test . > /dev/null 2>&1; then
        success "✅ Build local exitoso"

        # Test rápido del healthcheck
        log "Testeando healthcheck local..."

        # Ejecutar contenedor en background
        CONTAINER_ID=$(docker run -d -p 8001:8000 --env PORT=8000 agentos-test)

        # Esperar a que inicie
        sleep 10

        # Test healthcheck
        if curl -f http://localhost:8001/health > /dev/null 2>&1; then
            success "✅ Healthcheck local exitoso"
        else
            warning "⚠️  Healthcheck local falló (puede funcionar en Railway)"
        fi

        # Limpiar
        docker stop $CONTAINER_ID > /dev/null 2>&1
        docker rm $CONTAINER_ID > /dev/null 2>&1
        docker rmi agentos-test > /dev/null 2>&1

    else
        error "❌ Build local falló. Revisa Dockerfile.railway"
    fi
fi

# 5. Verificar variables de entorno necesarias
log "Verificando variables de entorno en Railway..."

REQUIRED_VARS=("DATABASE_URL" "REDIS_URL" "OPENAI_API_KEY" "CLERK_SECRET_KEY")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if ! railway variables get $var > /dev/null 2>&1; then
        MISSING_VARS+=($var)
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    warning "⚠️  Variables de entorno faltantes en Railway:"
    for var in "${MISSING_VARS[@]}"; do
        echo "   - $var"
    done

    read -p "¿Continuar con el deployment? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        error "Deployment cancelado. Configura las variables faltantes primero."
    fi
else
    success "✅ Variables de entorno configuradas"
fi

# 6. Mostrar información del deployment
log "Información del deployment:"
echo "  - Dockerfile: Dockerfile.railway"
echo "  - Configuración: railway.json"

# Mostrar configuración actual
if railway status > /dev/null 2>&1; then
    ENVIRONMENT=$(railway status --json | grep -o '"environment":"[^"]*' | cut -d'"' -f4)
    PROJECT=$(railway status --json | grep -o '"name":"[^"]*' | cut -d'"' -f4)
    echo "  - Proyecto: $PROJECT"
    echo "  - Ambiente: $ENVIRONMENT"
fi

# 7. Confirmación final
echo
read -p "¿Proceder con el deployment? (y/N): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log "Deployment cancelado por el usuario"
    exit 0
fi

# 8. Realizar deployment
log "🚀 Iniciando deployment a Railway..."
log "Tiempo estimado: 15-30 segundos"

# Capturar tiempo de inicio
START_TIME=$(date +%s)

# Ejecutar deployment
if railway up; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    success "🎉 Deployment completado en ${DURATION} segundos!"

    # Obtener URL del servicio
    if command -v railway &> /dev/null; then
        URL=$(railway status --json 2>/dev/null | grep -o '"url":"[^"]*' | cut -d'"' -f4 | head -1)
        if [ ! -z "$URL" ]; then
            success "🌐 Aplicación disponible en: $URL"
            success "🏥 Healthcheck: $URL/health"
            success "📊 Performance: $URL/api/v1/performance/summary"
        fi
    fi

    # Verificar healthcheck post-deployment
    if [ ! -z "$URL" ]; then
        log "Verificando healthcheck post-deployment..."
        sleep 5  # Esperar a que el servicio esté listo

        if curl -f "$URL/health" > /dev/null 2>&1; then
            success "✅ Healthcheck post-deployment exitoso"
        else
            warning "⚠️  Healthcheck post-deployment falló. Revisar logs con: railway logs"
        fi
    fi

    echo
    echo "📋 Comandos útiles post-deployment:"
    echo "   railway logs          - Ver logs en tiempo real"
    echo "   railway status        - Estado del servicio"
    echo "   railway shell         - Acceso shell al contenedor"
    echo "   railway metrics       - Métricas de uso"
    echo

else
    error "❌ Deployment falló. Revisar logs con: railway logs"
fi

log "Script completado!"