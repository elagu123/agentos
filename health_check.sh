#!/bin/bash
# AgentOS Health Check Script for Unix/Linux/macOS
# Usage: ./health_check.sh [options]

echo "Starting AgentOS Health Check..."

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Run health check with all provided arguments
python scripts/health_check.py "$@"
exit_code=$?

echo ""
if [ $exit_code -ne 0 ]; then
    echo "Health check completed with issues. Exit code: $exit_code"
    echo ""
    echo "Exit codes:"
    echo "  0 - All systems healthy"
    echo "  1 - Some systems degraded"
    echo "  2 - Critical systems unhealthy"
else
    echo "All systems are healthy!"
fi

exit $exit_code