@echo off
title GENNIE BOT - Assistente Executiva de Elite
chcp 65001 > nul
cls
echo =====================================================================
echo   INICIANDO GENNIE BOT - ASSISTENTE PESSOAL EXECUTIVA (TELEGRAM)
echo =====================================================================
echo.
cd /d "C:\Users\FAMÍLIA\Desktop\GENNIE_BOT"

if exist venv\Scripts\activate.bat (
    echo [OK] Ativando ambiente virtual venv...
    call venv\Scripts\activate.bat
)

echo [OK] Iniciando gennie.py...
echo Para encerrar o bot, feche esta janela ou pressione Ctrl+C.
echo.
python gennie.py

echo.
echo [!] O processo foi finalizado. Pressione qualquer tecla para sair...
pause > nul
