@echo off
cd /d "%~dp0"
echo Starting Claude History Viewer...
echo.
echo Server will be available at: http://localhost:8000
echo Press Ctrl+C to stop the server
echo.
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
