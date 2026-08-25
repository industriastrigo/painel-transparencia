@echo off
chcp 65001 >nul
title Painel da Transparencia - Instalacao
cd /d "%~dp0"

echo ============================================
echo   PAINEL DA TRANSPARENCIA - INSTALACAO
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [x] Python nao encontrado no PATH.
  echo     Instale em https://python.org e marque "Add to PATH".
  pause
  exit /b 1
)

if not exist ".venv" (
  echo [1/3] Criando ambiente virtual...
  python -m venv .venv
)

echo [2/3] Instalando dependencias...
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
  echo [x] Falha ao instalar dependencias.
  pause
  exit /b 1
)

echo [3/3] Verificando ambiente e fazendo a primeira carga...
echo      (IBGE + SICONFI das 27 UFs. Leva alguns minutos.)
python -m src.scripts.instalar --carga

echo.
echo Pronto. Use "ABRIR PAINEL.bat" para abrir.
pause
