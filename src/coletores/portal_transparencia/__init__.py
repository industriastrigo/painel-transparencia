"""Módulo Portal da Transparência (CGU)."""
from __future__ import annotations

from datetime import date
from ...nucleo import armazem, config, controle, rede
from ...nucleo.erros import ConfiguracaoAusente
from ...nucleo.registro import obter as obter_log

from .cliente import buscar_emendas, buscar_cartoes
from .parser import TIPOS_EMENDA, normalizar_emenda, normalizar_cartao
from .erros import ErroPortalTransparencia, diagnosticar_erro

log = obter_log("coletores.portal")
FONTE = "portal_transparencia"
TIPOS = TIPOS_EMENDA

def coletar_emendas(ano: int, paginas_max: int = 3000) -> int:
    if not config.CHAVE_PORTAL_TRANSPARENCIA:
        controle.gravar_marca(FONTE, f"emendas_{ano}", None, situacao="sem_chave",
                              detalhe="defina CHAVE_PORTAL_TRANSPARENCIA no .env")
        raise ConfiguracaoAusente(
            "o Portal da Transparência exige uma chave gratuita e ela não está configurada.",
            "Cadastre seu e-mail em portaldatransparencia.gov.br/api-de-dados/cadastrar-email "
            "e escreva o código recebido em CHAVE_PORTAL_TRANSPARENCIA no arquivo .env.")

    linhas, pagina = [], 1
    truncado = False

    while True:
        if pagina > paginas_max:
            truncado = True
            break
        lote = buscar_emendas(ano, pagina)
        if not lote:
            break
        for e in lote:
            linhas.append(normalizar_emenda(e, ano))
        pagina += 1

    if linhas:
        armazem.mesclar("emenda_parlamentar", linhas, FONTE)

    if truncado:
        log.warning("emendas de %d: a coleta parou no teto de %d páginas com %d linhas", ano, paginas_max, len(linhas))
    else:
        log.info("emendas de %d: %d linhas em %d página(s)", ano, len(linhas), pagina - 1)

    controle.gravar_marca(FONTE, f"emendas_{ano}", ano, len(linhas),
                          situacao="truncado" if truncado else "ok",
                          detalhe=f"teto de {paginas_max} páginas atingido" if truncado else "")
    return len(linhas)

def coletar_cartoes(ano: int, mes_inicio: int = 1, mes_fim: int = 12, paginas_max: int = 2000) -> int:
    if not config.CHAVE_PORTAL_TRANSPARENCIA:
        controle.gravar_marca(FONTE, f"cartoes_{ano}", None, situacao="sem_chave",
                              detalhe="defina CHAVE_PORTAL_TRANSPARENCIA no .env")
        raise ConfiguracaoAusente(
            "o Portal da Transparência exige uma chave gratuita e ela não está configurada.",
            "Cadastre seu e-mail em portaldatransparencia.gov.br/api-de-dados/cadastrar-email "
            "e escreva o código recebido em CHAVE_PORTAL_TRANSPARENCIA no arquivo .env.")

    linhas = []
    truncado = False

    for mes in range(mes_inicio, mes_fim + 1):
        mes_str = f"{mes:02d}/{ano}"
        pagina = 1
        while True:
            if pagina > paginas_max:
                truncado = True
                break
            lote = buscar_cartoes(mes_str, pagina)
            if not lote:
                break
            for c in lote:
                linhas.append(normalizar_cartao(c, ano, mes))
            pagina += 1

    if linhas:
        armazem.mesclar("cartao_corporativo", linhas, FONTE)

    controle.gravar_marca(FONTE, f"cartoes_{ano}", ano, len(linhas),
                          situacao="truncado" if truncado else "ok",
                          detalhe=f"teto de {paginas_max} páginas atingido" if truncado else "")
    return len(linhas)

def executar(anos: list[int] | None = None) -> None:
    for ano in anos or [date.today().year - 1, date.today().year]:
        try:
            coletar_emendas(ano)
            coletar_cartoes(ano)
        except ConfiguracaoAusente:
            raise
        except Exception as erro:  # noqa: BLE001
            log.error("coleta portal da transparencia %d falhou: %s", ano, erro)
