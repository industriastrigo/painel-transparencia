@echo off
chcp 65001 >nul
title Painel da Transparencia - Carga historica
cd /d "%~dp0"
call "%~dp0scripts\usar-python.bat"
if errorlevel 1 (
  pause
  exit /b 1
)

echo ============================================================
echo   CARGA HISTORICA - a serie inteira de cada fonte
echo ============================================================
echo.
echo Feita para rodar de madrugada. E RETOMAVEL: se a rede cair ou
echo voce fechar a janela, o que ja entrou fica gravado e a proxima
echo execucao continua de onde parou.
echo.
echo A maquina NAO vai dormir durante a coleta (a tela pode apagar).
echo.
echo   1 - Padrao      SADIPEM + transferencias + custos (5 recortes)
echo                   + RREO e RGF das 27 UFs, ano a ano
echo                   ~1 a 2 horas
echo   2 - Completa    o mesmo, mais o custo de pessoal ativo
echo                   ~15 horas: nao cabe numa noite, mas retoma
echo   3 - Municipios  SICONFI dos 5.570 municipios, ano a ano
echo                   ~3 horas POR ANO
echo   4 - Retomar     so o que ficou pendente da ultima vez
echo.
set /p opcao="Opcao: "

echo.
echo ------------------------------------------------------------
echo   GUARDAR A RESPOSTA INTEIRA (arquivo bruto)
echo ------------------------------------------------------------
echo.
echo Cada coletor le da resposta da API so as colunas que o painel
echo usa hoje - o resto e descartado na hora. Se amanha a pergunta
echo precisar de um campo que nao estava nessa lista, a unica saida
echo e coletar tudo de novo. E "tudo de novo" aqui sao HORAS: as
echo fontes limitam a uma requisicao por segundo.
echo.
echo Com o arquivo bruto ligado, cada resposta e gravada inteira,
echo como veio, em dados\bruto\. A pergunta de amanha se responde no
echo disco, em segundos, sem tocar na rede.
echo.
echo Custa disco (alguns GB), nao custa tempo de coleta.
echo Depois: CONSULTAR BRUTO.bat
echo.
set /p guardar="Guardar a resposta inteira? (S/n): "
set "bruto=--bruto"
if /i "%guardar%"=="n" set "bruto="

set "desde="
if "%opcao%"=="3" goto :municipios
echo.
set /p desde="Primeiro ano (Enter = inicio da serie de cada fonte): "
if not "%desde%"=="" set "desde=--desde %desde%"

if "%opcao%"=="1" goto :padrao
if "%opcao%"=="2" goto :completa
if "%opcao%"=="4" goto :padrao
goto :fim

:padrao
"%PY%" -m src.scripts.carga --tudo %bruto% %desde%
goto :fim

:completa
"%PY%" -m src.scripts.carga --tudo --com-pessoal-ativo %bruto% %desde%
goto :fim

:municipios
set /p ano="Ano do exercicio: "
"%PY%" -m src.scripts.coletar siconfi --nivel municipio --ano %ano% %bruto%
goto :fim

:fim
echo.
echo ------------------------------------------------------------
echo O resumo esta acima e tambem em logs\painel-AAAA-MM-DD.log
echo Rodar de novo continua de onde parou.
echo ------------------------------------------------------------
pause
