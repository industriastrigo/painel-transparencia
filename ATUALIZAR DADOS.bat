@echo off
chcp 65001 >nul
title Painel da Transparencia - Atualizacao de dados
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

echo Dica: com o painel aberto, a aba "Atualizar" faz tudo isto por
echo caixas de selecao, com progresso e log na tela. Este menu existe
echo para agendamento e para quando o painel nao esta no ar.
echo.
echo   1 - Diaria     Camara e Senado (projetos de lei e votos)
echo   2 - Mensal     SICONFI das 27 UFs + emendas
echo   3 - Municipios SICONFI dos 5.570 municipios (15-25 min, retomavel)
echo   4 - Municipios de UMA UF apenas
echo   5 - Anual      IBGE
echo   6 - Eleitoral  TSE
echo   7 - Situacao das fontes
echo   8 - Cidades que nao casaram (de-para TSE x IBGE)
echo.
set /p opcao="Opcao: "

set param_ano=
if not "%opcao%"=="7" if not "%opcao%"=="8" (
  set /p ano="Ano de referencia (Enter = padrao de cada fonte): "
)
if not "%ano%"=="" set param_ano=--ano %ano%

if "%opcao%"=="1" python -m src.scripts.coletar camara senado %param_ano%
if "%opcao%"=="2" python -m src.scripts.coletar siconfi portal_transparencia %param_ano%
if "%opcao%"=="3" (
  echo.
  echo Pode fechar no meio: a varredura retoma de onde parou.
  python -m src.scripts.coletar siconfi --nivel municipio %param_ano%
)
if "%opcao%"=="4" (
  set /p uf="Sigla da UF: "
  call python -m src.scripts.coletar siconfi --nivel municipio --uf %%uf%% %param_ano%
)
if "%opcao%"=="5" python -m src.scripts.coletar ibge
if "%opcao%"=="6" python -m src.scripts.coletar tse
if "%opcao%"=="7" python -m src.scripts.coletar --situacao
if "%opcao%"=="8" python -m src.scripts.coletar --pendencias

echo.
pause
