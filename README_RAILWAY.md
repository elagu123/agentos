# 🤖 AgentOS Backend

Multi-agent orchestration platform for SMEs with comprehensive business automation.

## 🚀 Deployment en Railway

### Quick Start (5 minutos)

1. **Fork/Clone este repo**
2. **Conectar a Railway**: [railway.app](https://railway.app)
3. **Deploy from GitHub repo**
4. **Configurar variables de entorno** (ver abajo)
5. **¡Listo!**

### 📋 Variables de Entorno Requeridas

```bash
# Base de datos (Railway la genera automáticamente)
DATABASE_URL=postgresql://user:pass@host:port/db

# Redis (Railway addon - $3/mes)
REDIS_URL=redis://host:port/0

# LLM APIs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_LLM_PROVIDER=openai

# Autenticación (Clerk.dev - gratuito)
CLERK_SECRET_KEY=sk_test_...
CLERK_PUBLISHABLE_KEY=pk_test_...

# Seguridad
SECRET_KEY=tu-jwt-secret-muy-seguro
ENCRYPTION_KEY=tu-fernet-key

# Email (Resend.com - gratuito)
RESEND_API_KEY=re_...
FROM_EMAIL=hello@tudominio.com

# CORS
ALLOWED_ORIGINS=https://tu-frontend.vercel.app,https://tudominio.com
```

## 🔧 Generar Keys de Seguridad

```bash
# JWT Secret (32+ caracteres)
openssl rand -base64 32

# Encryption Key (Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 📁 Estructura del Proyecto

```
├── app/
│   ├── api/              # Endpoints REST
│   ├── core/             # Lógica de negocio
│   ├── middleware/       # Seguridad y logging
│   ├── models/           # Modelos de datos
│   └── utils/            # Utilidades
├── scripts/              # Scripts de deployment
├── k8s/                  # Kubernetes (futuro)
├── monitoring/           # Observabilidad
└── tests/                # Tests automatizados
```

## 🛡 Seguridad

- Rate limiting automático
- Validación de entrada
- Headers de seguridad
- Protección XSS/SQL injection
- Autenticación JWT + Clerk

## 📊 Monitoreo

- Logs estructurados con structlog
- Health checks automáticos
- Métricas de performance
- Integración con Sentry

## 🔄 CI/CD

Railway hace deployment automático cuando pusheas a `main`.

## 📈 Escalabilidad

- **Starter**: $5-15/mes (MVP)
- **Growth**: $25-50/mes (startup)
- **Scale**: $100+/mes (empresa)

## 🆘 Support

- **Health**: `https://tu-app.railway.app/health`
- **Docs**: `https://tu-app.railway.app/docs`
- **Logs**: Railway dashboard

## 🚀 Features

- ✅ Multi-agent orchestration
- ✅ Business context analysis
- ✅ WhatsApp/Email integration
- ✅ Marketplace de agentes
- ✅ Feedback system
- ✅ Security dashboard
- ✅ Real-time monitoring

Made with ❤️ for SMEs worldwide