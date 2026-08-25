@echo off
chcp 65001 >nul
title Painel da Transparencia
cd /d "%~dp0"
call "%~dp0scripts\usar-python.bat"
if errorlevel 1 (
  pause
  exit /b 1
)

rem A porta e escolhida pelo script: se a preferida estiver numa faixa
rem reservada pelo Windows (Hyper-V/WinNAT), ele cai para a proxima livre
rem e imprime o endereco final na tela.
"%PY%" -m src.scripts.painel

if errorlevel 1 (
  echo.
  echo Se o Windows recusou a porta, tente uma explicita:
  echo     "%PY%" -m src.scripts.painel --porta 8123
)
pause
