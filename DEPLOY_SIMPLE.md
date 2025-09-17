# 🚀 AgentOS - Deployment Simple con Railway

## Costo Total Mensual: ~$15-25

- **Railway**: $5-10 (backend + base de datos)
- **Redis**: $3 (Railway addon)
- **Clerk Auth**: $0 (tier gratuito)
- **Resend Email**: $0 (tier gratuito)
- **Sentry**: $0 (tier gratuito)
- **Frontend**: $0 (Vercel/Netlify gratuito)

## 🛠 Pasos para Deployment

### 1. Preparar Repositorio
```bash
git add .
git commit -m "Setup Railway deployment"
git push origin main
```

### 2. Configurar Railway (2 minutos)
1. Ir a [railway.app](https://railway.app)
2. Login con GitHub
3. "New Project" → "Deploy from GitHub repo"
4. Seleccionar tu repositorio `agentos-backend`
5. Railway detecta automáticamente el Dockerfile

### 3. Configurar Variables de Entorno
En Railway dashboard:
- Ir a "Variables"
- Copiar contenido de `.env.railway`
- Pegar las variables una por una

### 4. Agregar Base de Datos
- Click "Add Service" → "PostgreSQL"
- Railway genera automáticamente `DATABASE_URL`

### 5. Agregar Redis (Opcional)
- Click "Add Service" → "Redis"
- Railway genera automáticamente `REDIS_URL`

### 6. Configurar Dominio
- En Railway: "Settings" → "Domains"
- Agregar dominio personalizado o usar el de Railway

## 🔧 Variables Críticas a Configurar

```env
# Obtener de OpenAI
OPENAI_API_KEY=sk-...

# Obtener de Clerk.dev (gratuito)
CLERK_SECRET_KEY=sk_test_...
CLERK_PUBLISHABLE_KEY=pk_test_...

# Generar con: openssl rand -base64 32
JWT_SECRET=...

# Generar con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=...

# Obtener de Resend.com (gratuito)
RESEND_API_KEY=re_...

# Tu dominio
ALLOWED_ORIGINS=https://tu-frontend.vercel.app
```

## 📱 Frontend en Vercel (Gratuito)
```bash
# En tu frontend
npm run build
vercel --prod
```

## 🔍 Verificación Post-Deployment
1. Health check: `https://tu-app.railway.app/health`
2. API docs: `https://tu-app.railway.app/docs`
3. Logs en Railway dashboard

## 🚨 Troubleshooting Común

### Error: Puerto
- Railway usa variable `PORT` automática
- No hardcodear puerto 8000

### Error: Base de datos
- Verificar que `DATABASE_URL` está configurada
- Railway la genera automáticamente

### Error: CORS
- Configurar `ALLOWED_ORIGINS` con dominio del frontend

## 📈 Escalabilidad Futura

Cuando necesites escalar:
1. **Railway Pro**: $20/mes (más recursos)
2. **DigitalOcean**: $25/mes (más control)
3. **AWS**: $50+/mes (enterprise ready)

## 🎯 Ventajas Railway vs AWS

| Feature | Railway | AWS |
|---------|---------|-----|
| Setup | 5 minutos | 2-3 horas |
| Costo inicial | $15/mes | $100+/mes |
| Maintenance | Automático | Manual |
| Escalabilidad | Limitada | Ilimitada |
| Ideal para | MVP/Startup | Enterprise |