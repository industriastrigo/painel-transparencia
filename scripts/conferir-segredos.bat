@echo off
rem Trava de seguranca: recusa publicar credencial ou acervo.
rem Chamado por CONFIGURAR GITHUB.bat e SALVAR NO GITHUB.bat.
setlocal
cd /d "%~dp0.."

git ls-files --error-unmatch .env >nul 2>nul
if not errorlevel 1 (
  echo   [x] .env esta versionado - ele guarda a chave da CGU.
  echo       Rode:  git rm --cached .env
  exit /b 1
)

git ls-files | findstr /b "dados/" >nul 2>nul
if not errorlevel 1 (
  echo   [x] A pasta dados/ esta versionada - sao ate 5 GB reproduziveis.
  echo       Rode:  git rm -r --cached dados
  exit /b 1
)

git diff --cached --name-only 2>nul | findstr /x ".env" >nul 2>nul
if not errorlevel 1 (
  echo   [x] .env esta no commit - remova com:  git restore --staged .env
  exit /b 1
)

echo   [ok] nenhum segredo a caminho do GitHub.
exit /b 0
