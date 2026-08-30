@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "scripts\usar-python.bat"
echo.
echo  ================================================================
echo   FAXINA DA PASTA
echo   Tira arquivo sem uso e log velho. NAO toca em dados.
echo  ================================================================
echo.
%PY% scripts\limpar.py
echo.
echo  ----------------------------------------------------------------
set /p ok="Apagar os itens acima? (s/N): "
if /i not "%ok%"=="s" goto fim
echo.
%PY% scripts\limpar.py --apagar
:fim
echo.
pause
