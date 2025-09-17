# 🚂 Railway Deployment Guide

## Paso 1: Preparar Repositorio

```bash
git add .
git commit -m "Initial Railway setup"
git push origin main
```

## Paso 2: Crear Proyecto en Railway

1. Ir a [railway.app](https://railway.app)
2. "Login with GitHub"
3. "New Project"
4. "Deploy from GitHub repo"
5. Seleccionar `agentos-backend`

## Paso 3: Configurar Variables de Entorno

Ir a proyecto > Variables > Add:

### Variables Críticas (REQUERIDAS)

```bash
# Generar con: openssl rand -base64 32
SECRET_KEY=TuSecretKeyMuySeguroAqui32Caracteres

# Generar con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=TuFernetKeyAqui

# OpenAI (requiere cuenta con billing)
OPENAI_API_KEY=sk-tu-api-key-de-openai

# Clerk.dev (tier gratuito)
CLERK_SECRET_KEY=sk_test_tu-clerk-secret
CLERK_PUBLISHABLE_KEY=pk_test_tu-clerk-public

# Resend.com (tier gratuito)
RESEND_API_KEY=re_tu-resend-key
FROM_EMAIL=hello@tudominio.com

# CORS - cambiar por tu dominio real
ALLOWED_ORIGINS=https://tu-frontend.vercel.app,https://tudominio.com
```

### Variables Opcionales

```bash
# Configuración de app
APP_NAME=AgentOS
ENVIRONMENT=production
DEBUG=false

# LLM adicionales (opcional)
ANTHROPIC_API_KEY=sk-ant-tu-key
DEFAULT_LLM_PROVIDER=openai
DEFAULT_MODEL=gpt-4o-mini

# Monitoring (opcional)
SENTRY_DSN=https://tu-sentry-dsn
```

## Paso 4: Agregar Base de Datos

1. En Railway: "Add Service"
2. "PostgreSQL"
3. Railway genera `DATABASE_URL` automáticamente

## Paso 5: Agregar Redis (Opcional)

1. "Add Service"
2. "Redis"
3. Railway genera `REDIS_URL` automáticamente
4. Costo: ~$3/mes

## Paso 6: Configurar Dominio

1. Settings > Domains
2. "Custom Domain" o usar `*.railway.app`

## Paso 7: Verificar Deployment

### Health Check
```bash
curl https://tu-app.railway.app/health
```

### API Docs
```bash
https://tu-app.railway.app/docs
```

## 🔧 Comandos Útiles

### Generar Keys Localmente
```bash
# Secret Key
openssl rand -base64 32

# Fernet Key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Ver Logs
1. Railway Dashboard
2. Tu proyecto > "View Logs"

### Redeploy
```bash
git add .
git commit -m "Update app"
git push origin main
```

## 🚨 Troubleshooting

### Error: "Application failed to respond"
- Verificar `PORT` environment variable
- Chequear logs en Railway dashboard

### Error: "Database connection failed"
- Verificar que PostgreSQL addon está activo
- `DATABASE_URL` debe estar configurada automáticamente

### Error: "CORS"
- Configurar `ALLOWED_ORIGINS` con dominio del frontend
- Incluir protocolo (https://)

### Error: "SECRET_KEY"
- Debe ser 32+ caracteres
- Generar con `openssl rand -base64 32`

## 💰 Costos Estimados

- **App + PostgreSQL**: $5-10/mes
- **Redis**: $3/mes
- **Bandwidth**: Incluido
- **Total**: ~$8-13/mes

## 🎯 Próximos Pasos

1. ✅ Backend deployed
2. 🔄 Deploy frontend (Vercel/Netlify)
3. 🔗 Conectar frontend con backend
4. 🧪 Testing en producción
5. 🚀 Go live!

## 📞 Soporte

- Railway Docs: [docs.railway.app](https://docs.railway.app)
- Discord: [railway.app/discord](https://railway.app/discord)
- GitHub Issues: Tu repositorio