@echo off
chcp 65001 >nul
title Auditoria de QA - Industrias Trigo
cd /d "%~dp0"

call "%~dp0scripts\usar-python.bat"
if errorlevel 1 (
  echo.
  echo [x] Erro ao localizar o interpretador Python.
  pause
  exit /b 1
)

echo ======================================================================
echo           INDUSTRIAS TRIGO - SUITE DE AUDITORIA TECNICA DE QA
echo ======================================================================
echo.
echo Executando bateria de testes automatizados (UI, Logica, API, DB e Batch)...
echo.

"%PY%" "%~dp0testes\qa_audit\runner_qa.py"

if errorlevel 1 (
  echo.
  echo [!] A bateria de testes finalizou com erros.
  echo     Verifique os detalhes no relatorio gerado.
) else (
  echo.
  echo [OK] Bateria de testes concluida com sucesso!
  echo [OK] Relatorio disponivel em: relatorio_auditoria_qa.html
  echo.
  echo Abrindo relatorio no navegador padrao...
  start "" "%~dp0relatorio_auditoria_qa.html"
)

echo.
pause
