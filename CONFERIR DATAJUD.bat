@echo off
chcp 65001 >nul
cd /d "%~dp0.."
call "scripts\usar-python.bat"
echo.
echo  Sonda da API Publica do DataJud (CNJ)
echo  Mostra o que a fonte devolve DE VERDADE, antes de existir coletor.
echo.
set /p trib="Tribunal (Enter = tjsp): "
if "%trib%"=="" set "trib=tjsp"
%PY% scripts\conferir_datajud.py --tribunal %trib% --salvar
echo.
pause
