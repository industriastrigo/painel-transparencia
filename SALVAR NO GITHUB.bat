@echo off
chcp 65001 >nul
title Painel da Transparencia - Salvar no GitHub
cd /d "%~dp0"

if not exist ".git" (
  echo [x] Este projeto ainda nao foi publicado.
  echo     Rode CONFIGURAR GITHUB.bat primeiro.
  pause
  exit /b 1
)

echo Conferindo que nenhum segredo vai junto...
call "%~dp0scripts\conferir-segredos.bat"
if errorlevel 1 (
  echo [x] Abortado: havia segredo prestes a ser publicado.
  pause
  exit /b 1
)

git add -A
git diff --cached --quiet
if not errorlevel 1 (
  echo Nada mudou desde o ultimo envio.
  timeout /t 3 >nul
  exit /b 0
)

echo.
echo O que mudou:
git diff --cached --stat
echo.
set /p mensagem="Descreva a alteracao (Enter = data e hora): "
if "%mensagem%"=="" set mensagem=Atualizacao de %date% %time:~0,5%

git commit -m "%mensagem%"
git push

if errorlevel 1 (
  echo.
  echo [x] O push falhou. Se alguem alterou o repositorio de outro
  echo     lugar, rode:  git pull --rebase   e tente de novo.
  pause
) else (
  echo.
  echo [ok] Enviado.
  timeout /t 3 >nul
)
