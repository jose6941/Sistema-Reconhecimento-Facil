@echo off
title Sistema de Reconhecimento Facial - TCC ESP32-CAM
echo ====================================================================
echo Iniciando Sistema de Reconhecimento Facial (TCC IFSP Birigui)
echo ====================================================================
echo.

:: Garante Node.js no PATH caso nao esteja registrado globalmente
set "PATH=C:\Program Files\nodejs;%PATH%"

echo [1/2] Iniciando Servidor Flask (Python - Processamento Facial & API)...
start "Backend Flask (Port 5000)" cmd /k ".\venv\Scripts\python.exe servidor_reconhecimento.py"

echo [2/2] Iniciando Painel Web Next.js (Port 3000)...
cd frontend
start "Frontend Next.js (Port 3000)" cmd /k "npm run dev"

echo.
echo ====================================================================
echo Sistema inicializado com sucesso!
echo - Backend API:  http://localhost:5000
echo - Painel Web:   http://localhost:3000
echo ====================================================================
echo.
pause
