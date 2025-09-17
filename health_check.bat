@echo off
REM AgentOS Health Check Script for Windows
REM Usage: health_check.bat [options]

echo Starting AgentOS Health Check...

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run health check with arguments
python scripts\health_check.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Health check completed with issues. Exit code: %ERRORLEVEL%
    echo.
    echo Exit codes:
    echo   0 - All systems healthy
    echo   1 - Some systems degraded
    echo   2 - Critical systems unhealthy
) else (
    echo.
    echo All systems are healthy!
)

pause