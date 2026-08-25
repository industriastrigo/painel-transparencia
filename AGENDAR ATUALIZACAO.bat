@echo off
chcp 65001 >nul
title Painel - Agendar atualizacao diaria
cd /d "%~dp0"
echo Cria uma tarefa no Windows que coleta Camara e Senado todo dia as 06:00.
echo.
schtasks /Create /SC DAILY /ST 06:00 /TN "PainelTransparencia-Diaria" ^
  /TR "\"%~dp0.venv\Scripts\python.exe\" -m src.scripts.coletar camara senado" /F
if errorlevel 1 (
  echo [x] Falhou. Rode este arquivo como administrador.
) else (
  echo [ok] Tarefa criada. Veja em Agendador de Tarefas do Windows.
)
pause
