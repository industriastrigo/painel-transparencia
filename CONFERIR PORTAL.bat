@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "scripts\usar-python.bat"
echo.
echo  Sonda das rotas novas do Portal da Transparencia (CGU)
echo  Mostra o que cada rota devolve DE VERDADE, antes de existir coletor.
echo.
set /p ano="Ano (Enter = 2025): "
if "%ano%"=="" set "ano=2025"
%PY% scripts\conferir_portal.py --ano %ano% --salvar
echo.
pause
