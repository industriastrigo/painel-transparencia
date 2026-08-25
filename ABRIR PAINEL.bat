@echo off
chcp 65001 >nul
title Painel da Transparencia
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

rem A porta e escolhida pelo script: se a preferida estiver numa faixa
rem reservada pelo Windows (Hyper-V/WinNAT), ele cai para a proxima livre
rem e imprime o endereco final na tela.
python -m src.scripts.painel

if errorlevel 1 (
  echo.
  echo Se o Windows recusou a porta, tente uma explicita:
  echo     python -m src.scripts.painel --porta 8123
)
pause
