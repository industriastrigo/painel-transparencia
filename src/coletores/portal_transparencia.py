"""Coletor Portal da Transparência (CGU) — emendas parlamentares.

Exige chave gratuita: cadastre o e-mail em
portaldatransparencia.gov.br/api-de-dados/cadastrar-email e ponha o valor em
CHAVE_PORTAL_TRANSPARENCIA no arquivo .env.

Sem chave, o coletor não quebra o pipeline: registra a pendência no controle
de ingestão e devolve zero, para que o painel mostre "sem dados" em vez de
número inventado.
"""

from __future__ import annotations

from datetime import date

from ..nucleo import armazem, config, controle, rede
from ..nucleo.erros import ConfiguracaoAusente
from ..nucleo.registro import obter as obter_log
from ..nucleo.valores import numero, opcional, texto

log = obter_log("coletores.portal")

FONTE = "portal_transparencia"

TIPOS = {
    "1": "Emenda individual",
    "2": "Emenda de bancada",
    "3": "Emenda de comissão",
    "4": "Emenda de relator (RP-9)",
    "5": "Transferência especial (Pix)",
}


def coletar_emendas(ano: int, paginas_max: int = 3000) -> int:
    if not config.CHAVE_PORTAL_TRANSPARENCIA:
        controle.gravar_marca(FONTE, f"emendas_{ano}", None, situacao="sem_chave",
                              detalhe="defina CHAVE_PORTAL_TRANSPARENCIA no .env")
        raise ConfiguracaoAusente(
            "o Portal da Transparência exige uma chave gratuita e ela não "
            "está configurada.",
            "Cadastre seu e-mail em portaldatransparencia.gov.br/"
            "api-de-dados/cadastrar-email e escreva o código recebido em "
            "CHAVE_PORTAL_TRANSPARENCIA, no arquivo .env da pasta do projeto.")

    linhas, pagina = [], 1
    truncado = False

    while True:
        if pagina > paginas_max:
            # O teto existe para não rodar para sempre se a API paginar de
            # forma estranha. Bater nele em silêncio, porém, produz uma
            # coleta pela metade com cara de completa: foram exatamente
            # 3.000 linhas (200 páginas × 15) parecendo o total das emendas.
            truncado = True
            break

        lote = rede.buscar(FONTE, f"{config.PORTAL_TRANSPARENCIA}/emendas",
                           {"ano": ano, "pagina": pagina})
        if not lote:
            break
        for e in lote:
            linhas.append({
                "ano": int(ano),
                "codigo_emenda": texto(e.get("codigoEmenda")),
                "tipo_emenda": opcional(e.get("tipoEmenda")),
                "autor": opcional(e.get("nomeAutor")),
                "numero_emenda": opcional(e.get("numeroEmenda")),
                "funcao": opcional(e.get("funcao")),
                "subfuncao": opcional(e.get("subfuncao")),
                # A CGU devolve os valores como TEXTO no formato brasileiro
                # ("1.234.567,89"). Guardá-los crus fazia o tipo declarado
                # falhar ("não coube em DOUBLE") e a coluna virar string —
                # quebrando qualquer soma ou ordenação depois.
                "valor_empenhado": numero(e.get("valorEmpenhado")),
                "valor_liquidado": numero(e.get("valorLiquidado")),
                "valor_pago": numero(e.get("valorPago")),
                "valor_resto_pago": numero(e.get("valorRestoInscrito")),
                "localidade": opcional(e.get("localidadeDoGasto")),
                "data_referencia": f"{ano}-12-31",
            })
        pagina += 1

    if linhas:
        armazem.mesclar("emenda_parlamentar", linhas, FONTE)

    if truncado:
        log.warning(
            "emendas de %d: a coleta parou no teto de %d páginas com %d "
            "linhas — provavelmente há mais. Aumente `paginas_max` e rode de "
            "novo; nada duplica.", ano, paginas_max, len(linhas))
    else:
        log.info("emendas de %d: %d linhas em %d página(s)",
                 ano, len(linhas), pagina - 1)

    controle.gravar_marca(FONTE, f"emendas_{ano}", ano, len(linhas),
                          situacao="truncado" if truncado else "ok",
                          detalhe=f"teto de {paginas_max} páginas atingido"
                          if truncado else "")
    return len(linhas)


def executar(anos: list[int] | None = None) -> None:
    for ano in anos or [date.today().year - 1, date.today().year]:
        try:
            coletar_emendas(ano)
        except ConfiguracaoAusente:
            # Sobe intacta: quem chama precisa distinguir "falta configurar"
            # de "deu erro". Repetir nos outros anos não adiantaria nada.
            raise
        except Exception as erro:  # noqa: BLE001
            log.error("emendas %d falharam: %s", ano, erro)


if __name__ == "__main__":
    executar()
