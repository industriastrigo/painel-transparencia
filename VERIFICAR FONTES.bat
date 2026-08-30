@echo off
chcp 65001 >nul
title Painel da Transparencia - Verificacao das fontes
cd /d "%~dp0"
call "%~dp0scripts\usar-python.bat"
if errorlevel 1 (
  pause
  exit /b 1
)

echo ============================================================
echo   VERIFICACAO DAS FONTES
echo ============================================================
echo.
echo Faz cerca de dez requisicoes e NAO grava nada no acervo.
echo Serve para conferir que os consertos pegaram, antes de rodar
echo uma coleta de horas em cima de suposicao.
echo.
echo A saida vai para logs\verificacao.txt tambem.
echo.

echo Acompanhe abaixo. Leva menos de um minuto.
echo.

rem Sem redirecionar: o proprio script escreve na tela e no arquivo ao mesmo
rem tempo. Redirecionar deixava a janela muda ate o fim, e uma janela muda e
rem indistinguivel de uma janela travada.
"%PY%" -m src.scripts.verificar

echo.
echo ------------------------------------------------------------
echo Salvo tambem em logs\verificacao.txt
echo ------------------------------------------------------------
pause
