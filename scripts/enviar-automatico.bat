@echo off
rem Envio automatico diario. Sem perguntas: roda sem ninguem olhando.
rem Se a trava de segredos reprovar, NAO envia e registra o motivo.
cd /d "%~dp0.."

call "%~dp0conferir-segredos.bat" >> "logs\github.log" 2>&1
if errorlevel 1 (
  echo %date% %time% ABORTADO: segredo detectado >> "logs\github.log"
  exit /b 1
)

git add -A
git diff --cached --quiet && (
  echo %date% %time% nada a enviar >> "logs\github.log"
  exit /b 0
)

git commit -m "Envio automatico de %date%" >> "logs\github.log" 2>&1
git push >> "logs\github.log" 2>&1
echo %date% %time% envio concluido >> "logs\github.log"
