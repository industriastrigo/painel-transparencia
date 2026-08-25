@echo off
rem Resolve qual interpretador usar e devolve em %PY%.
rem Chamado com CALL pelos lancadores da pasta raiz.
rem
rem POR QUE NAO USAR activate.bat
rem
rem O activate guarda o CAMINHO ABSOLUTO da pasta onde o ambiente foi criado.
rem Renomear a pasta do projeto — ou move-la de lugar — invalida esse caminho.
rem O activate entao nao tem efeito, o "python" seguinte e o do sistema, e o
rem erro que aparece e "ModuleNotFoundError: No module named 'uvicorn'", que
rem parece falta de instalacao e nao e.
rem
rem Chamar .venv\Scripts\python.exe direto sobrevive a mudanca de pasta: o
rem Python descobre o ambiente pela localizacao do proprio executavel.

set "PY="
if exist ".venv\Scripts\python.exe" goto :tem_venv

where python >nul 2>nul
if errorlevel 1 goto :sem_python
set "PY=python"
echo [!] Sem ambiente .venv - usando o Python do sistema.
echo     Rode INSTALAR.bat para criar o ambiente do projeto.
exit /b 0

:tem_venv
set "PY=.venv\Scripts\python.exe"
".venv\Scripts\python.exe" -c "import uvicorn, fastapi, duckdb" >nul 2>nul
if errorlevel 1 goto :incompleto
exit /b 0

:incompleto
echo [!] O ambiente .venv existe mas esta sem as dependencias.
echo     Rode INSTALAR.bat para completa-lo.
exit /b 0

:sem_python
echo [x] Python nao encontrado no PATH.
echo     Instale em https://python.org e marque "Add to PATH".
exit /b 1
