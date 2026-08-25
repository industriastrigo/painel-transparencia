@echo off
chcp 65001 >nul
title Painel da Transparencia - Agendar envio diario
cd /d "%~dp0"

if not exist ".git" (
  echo [x] Publique primeiro com CONFIGURAR GITHUB.bat.
  pause
  exit /b 1
)

echo Cria uma tarefa que envia ao GitHub todo dia as 19:00.
echo.
echo Por que diario, e nao a cada alteracao: um commit por salvamento
echo produz centenas de mensagens iguais e nenhuma conta o que mudou.
echo Uma vez por dia mantem o historico legivel e ainda nao depende
echo de voce lembrar de enviar.
echo.

schtasks /Create /SC DAILY /ST 19:00 /TN "PainelTransparencia-GitHub" ^
  /TR "\"%~dp0scripts\enviar-automatico.bat\"" /F

if errorlevel 1 (
  echo [x] Falhou. Rode este arquivo como administrador.
) else (
  echo [ok] Agendado. Para cancelar:
  echo      schtasks /Delete /TN "PainelTransparencia-GitHub" /F
)
pause
