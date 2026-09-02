@echo off
chcp 65001 >nul
title Painel da Transparencia - Atualizacao de dados
cd /d "%~dp0"
call "%~dp0scripts\usar-python.bat"
if errorlevel 1 (
  pause
  exit /b 1
)

echo Dica: com o painel aberto, a aba "Atualizar" faz tudo isto por
echo caixas de selecao, com progresso e log na tela. Este menu existe
echo para agendamento e para quando o painel nao esta no ar.
echo.
echo   0 - TUDO       todas as fontes de uma vez (so pergunta o ano)
echo   1 - Diaria     Camara e Senado (projetos de lei e votos)
echo   2 - Mensal     SICONFI das 27 UFs + emendas
echo   3 - Municipios SICONFI dos 5.570 municipios (30-50 min, retomavel)
echo   4 - Municipios de UMA UF apenas
echo   5 - Anual      IBGE
echo   6 - Eleitoral  TSE
echo   7 - Repasses   Transferencias da Uniao (FPM, FPE, FUNDEB)
echo   8 - Credito    SADIPEM (operacoes de credito)
echo   F - Fiscal     Saude, educacao e limites da LRF (RREO e RGF)
echo   9 - Situacao das fontes
echo   L - Cidades que nao casaram (de-para TSE x IBGE)
echo.
set /p opcao="Opcao: "

rem Consulta nao coleta nada, entao nao faz sentido perguntar o ano.
set "param_ano="
set "ano="
if /i "%opcao%"=="9" goto :executar
if /i "%opcao%"=="L" goto :executar

echo.
echo O ano vazio deixa cada fonte usar o padrao dela: a Camara busca o ano
echo corrente, o SICONFI o exercicio anterior (o atual ainda nao fechou).
set /p ano="Ano de referencia (Enter = padrao de cada fonte): "
if not "%ano%"=="" set "param_ano=--ano %ano%"

:executar
if "%opcao%"=="0" goto :tudo
if "%opcao%"=="1" "%PY%" -m src.scripts.coletar camara senado %param_ano%
if "%opcao%"=="2" "%PY%" -m src.scripts.coletar siconfi portal_transparencia %param_ano%
if "%opcao%"=="3" goto :municipios
if "%opcao%"=="4" goto :uma_uf
if "%opcao%"=="5" "%PY%" -m src.scripts.coletar ibge
if "%opcao%"=="6" "%PY%" -m src.scripts.coletar tse %param_ano%
if "%opcao%"=="7" "%PY%" -m src.scripts.coletar transferencias %param_ano%
if "%opcao%"=="8" "%PY%" -m src.scripts.coletar sadipem
if /i "%opcao%"=="F" "%PY%" -m src.scripts.coletar siconfi_funcao siconfi_rgf %param_ano%
if /i "%opcao%"=="9" "%PY%" -m src.scripts.coletar --situacao
if /i "%opcao%"=="L" "%PY%" -m src.scripts.coletar --pendencias
goto :fim

:tudo
echo.
echo Roda TODAS as fontes na ordem certa: referencias, IBGE, SICONFI
echo (contas anuais, RREO e RGF), transferencias, SADIPEM, Camara,
echo Senado, TSE, emendas e Tesouro.
echo.
echo Isto inclui as 27 UFs do SICONFI, nao os 5.570 municipios - a
echo varredura municipal e a opcao 3, porque leva de 30 a 50 minutos e
echo tem cadencia propria. Uma fonte que falhar nao derruba as outras.
echo.
set /p municipios="Incluir tambem os 5.570 municipios? (s/N): "
if /i "%municipios%"=="s" goto :tudo_com_municipios

"%PY%" -m src.scripts.coletar --tudo %param_ano%
goto :fim

:tudo_com_municipios
echo.
echo Pode fechar no meio: a varredura municipal retoma de onde parou.
"%PY%" -m src.scripts.coletar --tudo --nivel todos %param_ano%
goto :fim

:municipios
echo.
echo Pode fechar no meio: a varredura retoma de onde parou.
"%PY%" -m src.scripts.coletar siconfi --nivel municipio %param_ano%
goto :fim

:uma_uf
set /p uf="Sigla da UF: "
call "%PY%" -m src.scripts.coletar siconfi --nivel municipio --uf %%uf%% %param_ano%
goto :fim

:fim
echo.
pause
