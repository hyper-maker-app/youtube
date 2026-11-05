@echo off
title Muse AI Gateway (Port 18610)
cd /d "%~dp0..\gateways\museai"
echo ===================================================
echo   Starting Muse AI OpenAI-Compatible Gateway
echo   Endpoint: http://127.0.0.1:18610/v1
echo   CDP Port: 19210 (Isolated from Flow Port 9223)
echo ===================================================
python -m museai
pause
