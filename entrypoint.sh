#!/bin/bash
set -e

echo "🚀 Starting AgentOS EntryPoint"
echo "📊 PORT: ${PORT:-8000}"
echo "📍 Environment: ${ENVIRONMENT:-development}"

# Check if DATABASE_URL exists and convert if needed
if [ -n "$DATABASE_URL" ]; then
    echo "✅ DATABASE_URL found"
    if [[ "$DATABASE_URL" == postgresql://* ]]; then
        echo "🔄 Converting postgresql:// to postgresql+asyncpg://"
        export DATABASE_URL="${DATABASE_URL/postgresql:\/\//postgresql+asyncpg:\/\/}"
    fi
else
    echo "❌ DATABASE_URL not found"
fi

# Start the application
echo "🎯 Starting Uvicorn server..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}