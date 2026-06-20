@echo off
echo ==========================================
echo Killing process listening on port 8000...
echo ==========================================

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo Found process %%a on port 8000. Killing it now...
    taskkill /F /PID %%a
)

echo Port 8000 is now free.
pause
