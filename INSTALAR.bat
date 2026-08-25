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

rem Ambiente que existe mas nao roda mais: acontece quando o Python que o
rem criou foi desinstalado ou atualizado de versao. Refazer custa um minuto;
rem diagnosticar o erro que ele produz custa uma tarde.
if not exist ".venv\Scripts\python.exe" goto :criar
".venv\Scripts\python.exe" --version >nul 2>nul
if not errorlevel 1 goto :tem_ambiente
echo [1/3] O ambiente .venv existe mas nao executa - refazendo...
python -m venv .venv --clear
goto :tem_ambiente

:criar
echo [1/3] Criando ambiente virtual...
python -m venv .venv

:tem_ambiente

echo [2/3] Instalando dependencias...
rem O executavel do ambiente, direto: activate.bat guarda o caminho absoluto
rem da criacao e para de funcionar se a pasta do projeto for renomeada.
set "PY=.venv\Scripts\python.exe"
"%PY%" -m pip install --upgrade pip --quiet
"%PY%" -m pip install -r requirements.txt --quiet
if errorlevel 1 (
  echo [x] Falha ao instalar dependencias.
  pause
  exit /b 1
)

echo [3/3] Verificando ambiente e fazendo a primeira carga...
echo      (IBGE + SICONFI das 27 UFs. Leva alguns minutos.)
"%PY%" -m src.scripts.instalar --carga

echo.
echo Pronto. Use "ABRIR PAINEL.bat" para abrir.
pause
