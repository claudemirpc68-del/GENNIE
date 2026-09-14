@echo off
title RENOVAR AUTORIZAÇÃO DO GMAIL - GENNIE BOT
chcp 65001 > nul
cls
echo =====================================================================
echo   RENOVAÇÃO DE ACESSO DO GMAIL (GENNIE BOT)
echo =====================================================================
echo.
echo Uma janela do navegador será aberta para você fazer login no Google.
echo Selecione sua conta (claudemirpc68@gmail.com) e clique em "Permitir".
echo.
cd /d "C:\Users\FAMÍLIA\Desktop\GENNIE_BOT"

if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

python autorizar.py

echo.
echo =====================================================================
echo Pronto! Autorização renovada. Você já pode usar a GENNIE no Telegram!
echo =====================================================================
echo.
pause
