@echo off
chcp 65001 >nul
title Painel da Transparencia - Arquivo bruto
cd /d "%~dp0"
call "%~dp0scripts\usar-python.bat"
if errorlevel 1 (
  pause
  exit /b 1
)

echo ============================================================
echo   ARQUIVO BRUTO - a resposta da fonte, como ela veio
echo ============================================================
echo.
echo Aqui esta guardado o que a API respondeu INTEIRO, antes de o
echo coletor escolher as colunas. Serve para responder uma pergunta
echo nova sem gastar outra madrugada de coleta.
echo.
echo   1 - Inventario  o que existe guardado, e quanto ocupa
echo   2 - Campos      TODOS os campos que uma fonte mandou,
echo                   inclusive os que nenhum coletor le
echo   3 - Ver         uma resposta inteira, como veio
echo   4 - SQL         qualquer pergunta, com a tabela `bruto` pronta
echo   5 - Reprocessar roda o coletor lendo do arquivo, SEM rede
echo.
set /p opcao="Opcao: "

if "%opcao%"=="1" goto :inventario
if "%opcao%"=="2" goto :campos
if "%opcao%"=="3" goto :ver
if "%opcao%"=="4" goto :sql
if "%opcao%"=="5" goto :reprocessar
goto :fim

:inventario
"%PY%" -m src.scripts.bruto
goto :fim

:campos
echo.
echo A fonte e o recurso saem do inventario (opcao 1).
echo Exemplo: fonte "siconfi", recurso "rreo".
set /p fonte="Fonte: "
set /p recurso="Recurso: "
"%PY%" -m src.scripts.bruto --campos %fonte% %recurso%
goto :fim

:ver
set /p fonte="Fonte: "
set /p recurso="Recurso: "
"%PY%" -m src.scripts.bruto --ver %fonte% %recurso%
goto :fim

:sql
echo.
echo Colunas: fonte, recurso, dia, url, parametros, formato, carga,
echo bytes, coletado_em. A resposta inteira esta em `carga`.
echo Exemplo: SELECT fonte, recurso, COUNT(*) FROM bruto GROUP BY 1,2
echo.
set /p consulta="SQL: "
"%PY%" -m src.scripts.bruto --sql "%consulta%"
goto :fim

:reprocessar
echo.
echo Roda o coletor de novo, mas lendo do arquivo em vez da rede.
echo E assim que um campo que passou a ser lido HOJE entra no acervo
echo a partir da resposta guardada ONTEM - sem uma requisicao sequer.
echo.
echo O que nao estiver guardado ainda sera buscado na rede.
echo.
set /p fonte="Fonte (ex.: siconfi): "
set /p ano="Ano (Enter = padrao da fonte): "
if "%ano%"=="" goto :reprocessar_sem_ano
"%PY%" -m src.scripts.bruto --reprocessar %fonte% --ano %ano%
goto :fim

:reprocessar_sem_ano
"%PY%" -m src.scripts.bruto --reprocessar %fonte%
goto :fim

:fim
echo.
pause
