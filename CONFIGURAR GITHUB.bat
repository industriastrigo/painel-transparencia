@echo off
chcp 65001 >nul
title Painel da Transparencia - Configurar GitHub
cd /d "%~dp0"

echo ============================================================
echo   PUBLICAR NO GITHUB - configuracao inicial (uma vez so)
echo ============================================================
echo.

where git >nul 2>nul
if errorlevel 1 (
  echo [x] Git nao encontrado.
  echo     Instale o GitHub Desktop ^(github.com/apps/desktop^) ou
  echo     o Git for Windows ^(git-scm.com^) e rode este arquivo de novo.
  pause
  exit /b 1
)

echo Antes de continuar, crie o repositorio VAZIO no GitHub:
echo   1. Entre na conta das Industrias Trigo
echo   2. New repository
echo   3. Nome: painel-transparencia
echo   4. NAO marque "Add a README" nem "Add .gitignore"
echo   5. Create repository
echo.
set /p usuario="Usuario ou organizacao no GitHub (ex.: industriastrigo): "
if "%usuario%"=="" (
  echo [x] Sem usuario nao da para continuar.
  pause
  exit /b 1
)
set /p repo="Nome do repositorio [painel-transparencia]: "
if "%repo%"=="" set repo=painel-transparencia

rem O nome do repositorio nao leva ".git" - isso e sufixo da URL, e digitado
rem aqui viraria painel-transparencia.git.git no endereco final.
if /i "%repo:~-4%"==".git" set "repo=%repo:~0,-4%"

if not exist ".git" (
  echo.
  echo [1/5] Criando o repositorio local...
  git init -b main
) else (
  echo [1/5] Repositorio local ja existe.
)
git branch -M main >nul 2>nul

echo [2/5] Conferindo identidade...
set "email="
set "nome="
for /f "delims=" %%i in ('git config user.email 2^>nul') do set "email=%%i"
for /f "delims=" %%i in ('git config user.name 2^>nul') do set "nome=%%i"
if not defined email goto :pedir_identidade
if not defined nome goto :pedir_identidade
goto :identidade_pronta

:pedir_identidade
echo     O git ainda nao sabe quem assina os commits.
set /p email="    Seu e-mail do GitHub: "
set /p nome="    Seu nome: "
git config user.email "%email%"
git config user.name "%nome%"

set "email="
for /f "delims=" %%i in ('git config user.email 2^>nul') do set "email=%%i"
if not defined email (
  echo [x] Nao consegui gravar a identidade. Rode na mao, nesta pasta:
  echo       git config --global user.email "voce@exemplo.com"
  echo       git config --global user.name "Seu Nome"
  pause
  exit /b 1
)

:identidade_pronta
echo     assinando como %nome% ^<%email%^>

echo [3/5] Conferindo que nenhum segredo vai junto...
call "%~dp0scripts\conferir-segredos.bat"
if errorlevel 1 (
  echo [x] Abortado: havia segredo prestes a ser publicado.
  pause
  exit /b 1
)

echo [4/5] Primeiro commit...
git add -A
git commit -m "Painel da Transparencia: primeira publicacao"
git rev-parse --verify HEAD >nul 2>nul
if errorlevel 1 (
  echo.
  echo [x] Nenhum commit foi criado - sem commit nao ha o que enviar.
  echo     A mensagem do git logo acima diz o motivo.
  pause
  exit /b 1
)

echo [5/5] Enviando para o GitHub...
git remote remove origin 2>nul
git remote add origin https://github.com/%usuario%/%repo%.git
git push -u origin main
if not errorlevel 1 goto :publicado

echo.
echo     O primeiro envio falhou. Tentando de novo, caso o repositorio
echo     ja tenha um README criado pelo GitHub...
git pull --rebase origin main
git push -u origin main
if not errorlevel 1 goto :publicado

echo.
echo [x] O push falhou. As duas causas possiveis:
echo.
echo     1. Falta autenticar. Abra o GitHub Desktop, entre na conta das
echo        Industrias Trigo uma vez, feche e rode este arquivo de novo.
echo.
echo     2. O endereco esta errado. Confira que
echo        https://github.com/%usuario%/%repo%  abre no navegador.
echo.
pause
exit /b 1

:publicado
echo.
echo [ok] Publicado em https://github.com/%usuario%/%repo%
echo      Daqui em diante use SALVAR NO GITHUB.bat
pause
