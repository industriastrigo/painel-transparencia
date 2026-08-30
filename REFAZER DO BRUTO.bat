@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "scripts\usar-python.bat"
echo.
echo  ================================================================
echo   REFAZER DO ARQUIVO BRUTO  (sem internet)
echo   Reconstroi despesa_funcao e indicador_fiscal a partir das
echo   respostas ja guardadas. Nao recoleta nada.
echo  ================================================================
echo.
%PY% -m src.nucleo.reprocessar despesa_funcao indicador_fiscal --ensaio
echo.
echo  ----------------------------------------------------------------
echo  A regra de leitura mudou (bloco intra/exceto-intra), entao as
echo  tabelas serao APAGADAS antes de refazer. Isso e necessario: os
echo  sk antigos nao casam com os novos e as duas versoes conviveriam.
echo.
set /p ok="Refazer do zero? (s/N): "
if /i not "%ok%"=="s" goto fim
echo.
%PY% -m src.nucleo.reprocessar despesa_funcao indicador_fiscal --do-zero
:fim
echo.
pause
