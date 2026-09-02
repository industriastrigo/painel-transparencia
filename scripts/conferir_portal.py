"""Sonda das rotas NOVAS do Portal da Transparência (CGU).

Hoje o projeto usa uma única rota da CGU: `/emendas`. Este arquivo confere as
que pretendemos usar em seguida, **antes** de existir coletor — pela regra da
armadilha 12 do `docs/08-armadilhas.md`: documentação não é contrato.

Aqui a dúvida não é se a API responde (o coletor de emendas prova que sim,
com a mesma chave). É se cada rota nova devolve o que o Swagger promete, e
quanto ela devolve — algumas exigem um filtro obrigatório que a documentação
descreve vagamente como "ao menos um dos demais filtros".

Também é um **freio de privacidade**. Esta API tem duas versões de quase todo
benefício social: uma agregada por município (valor + quantidade, sem
pessoa) e outra nominal (nome, CPF e NIS de cada beneficiário). O painel usa
só a agregada. A sonda recusa qualquer rota da lista negra e grita se um
campo de pessoa aparecer onde não deveria.

Uso:
    python scripts/conferir_portal.py
    python scripts/conferir_portal.py --ano 2025 --salvar
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.nucleo import config, rede  # noqa: E402

FONTE = "portal_transparencia"

# Rotas que este projeto NUNCA chama. Não é limitação técnica: beneficiário
# de programa social não é agente público, e um painel sobre o gasto dos
# poderes não tem por que publicar o nome e o CPF de quem recebe Bolsa
# Família. A versão agregada por município responde à mesma pergunta
# — quanto o programa custa aqui — sem expor ninguém.
PROIBIDAS = (
    "bolsa-familia-sacado-por-nis",
    "bolsa-familia-disponivel-por-cpf-ou-nis",
    "bolsa-familia-sacado-beneficiario-por-municipio",
    "bolsa-familia-disponivel-beneficiario-por-municipio",
    "novo-bolsa-familia-sacado-por-nis",
    "novo-bolsa-familia-sacado-beneficiario-por-municipio",
    "auxilio-brasil-sacado-por-nis",
    "auxilio-brasil-sacado-beneficiario-por-municipio",
    "bpc-por-cpf-ou-nis", "bpc-beneficiario-por-municipio",
    "peti-por-cpf-ou-nis", "peti-beneficiario-por-municipio",
    "safra-codigo-por-cpf-ou-nis", "safra-beneficiario-por-municipio",
    "seguro-defeso-codigo", "seguro-defeso-beneficiario-por-municipio",
    "auxilio-emergencial-por-cpf-ou-nis",
    "auxilio-emergencial-beneficiario-por-municipio",
    # Perfilamento: dado um CPF, devolve 28 sinalizadores dizendo se a
    # pessoa recebe benefício, é servidora, foi sancionada. Isso é máquina
    # de dossiê, não transparência de gasto público.
    "pessoa-fisica",
)

# Campos de pessoa. Alguns são legítimos em rota de agente público (o nome
# de quem viajou a serviço), mas nenhum deles pode aparecer numa rota que
# deveria ser agregada — daí a checagem ser por rota, não global.
CAMPOS_DE_PESSOA = ("cpfFormatado", "nis", "numeroInscricaoSocial",
                    "cpfPunidoFormatado", "cpf", "nomeInstituidor",
                    "cpfInstituidor", "cpfRepresentanteLegal")

# (rótulo, caminho, parâmetros, precisa_ser_agregada)
def _sondas(ano: int) -> list[tuple[str, str, dict, bool]]:
    return [
        ("órgãos SIAFI (dimensão)", "orgaos-siafi", {"pagina": 1}, True),
        ("órgãos SIAPE (dimensão)", "orgaos-siape", {"pagina": 1}, True),
        ("funções e cargos (dimensão)", "servidores/funcoes-e-cargos",
         {"pagina": 1}, True),
        # O prato principal: força de trabalho AGREGADA por órgão. É o que
        # falta ao painel desde que `pessoal_ativo` ficou pela metade — e não
        # traz uma linha de dado pessoal.
        ("servidores por órgão (agregado)", "servidores/por-orgao",
         {"pagina": 1}, True),
        # Despesa federal. O RREO cobre estados e municípios; isto cobre a
        # União, e na MESMA classificação por função da Portaria 42/1999.
        ("despesa federal por órgão", "despesas/por-orgao",
         {"ano": ano, "orgaoSuperior": "26000", "pagina": 1}, True),
        ("despesa federal por função", "despesas/por-funcional-programatica",
         {"ano": ano, "funcao": "12", "pagina": 1}, True),
        # Agentes públicos nomeados: aqui o nome é legítimo (é o gasto DELE,
        # a serviço), mas a sonda mostra o que vem para a decisão ser sua.
        ("viagens a serviço", "viagens",
         {"dataIdaDe": f"01/03/{ano}", "dataIdaAte": f"31/03/{ano}",
          "dataRetornoDe": f"01/03/{ano}", "dataRetornoAte": f"30/04/{ano}",
          "codigoOrgao": "26000", "pagina": 1}, False),
        ("cartão de pagamento", "cartoes",
         {"mesExtratoInicio": f"01/{ano}", "mesExtratoFim": f"03/{ano}",
          "codigoOrgao": "26000", "pagina": 1}, False),
        ("imóveis funcionais", "imoveis", {"pagina": 1}, True),
        ("ocupantes de imóvel funcional", "permissionarios",
         {"pagina": 1}, False),
    ]


def achatar(objeto, prefixo: str = "") -> dict[str, str]:
    plano: dict[str, str] = {}
    if isinstance(objeto, dict):
        for chave, valor in objeto.items():
            plano.update(achatar(valor, f"{prefixo}.{chave}" if prefixo else chave))
    elif isinstance(objeto, list):
        plano[f"{prefixo}[]"] = f"lista({len(objeto)})"
        if objeto:
            plano.update(achatar(objeto[0], f"{prefixo}[]"))
    else:
        plano[prefixo] = type(objeto).__name__
    return plano


def pessoais(campos) -> list[str]:
    achados = []
    for campo in campos:
        curto = campo.split(".")[-1].replace("[]", "")
        if curto in CAMPOS_DE_PESSOA:
            achados.append(campo)
    return achados


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", type=int, default=2025)
    ap.add_argument("--salvar", action="store_true",
                    help="grava as respostas cruas em dados/bruto/portal/")
    args = ap.parse_args()

    if not config.CHAVE_PORTAL_TRANSPARENCIA:
        print("✗ CHAVE_PORTAL_TRANSPARENCIA não está no .env.")
        print("  Cadastre em portaldatransparencia.gov.br/api-de-dados/"
              "cadastrar-email e cole a chave pelo painel.")
        return 1
    print(f"chave presente (…{config.CHAVE_PORTAL_TRANSPARENCIA[-4:]})")
    print(f"freio: {rede.intervalo_de(FONTE):.2f}s entre chamadas "
          f"(~{60 / max(rede.intervalo_de(FONTE), 0.01):.0f}/min; a CGU "
          "permite 400/min das 6h às 23h59 e 700/min de madrugada)\n")

    problemas = 0
    for rotulo, caminho, parametros, agregada in _sondas(args.ano):
        if any(p in caminho for p in PROIBIDAS):
            print(f"✗ {rotulo}: rota na lista negra, não consulto.")
            continue

        print(f"── {rotulo}")
        print(f"   GET /{caminho}  {parametros}")
        try:
            dados = rede.buscar(FONTE,
                                f"{config.PORTAL_TRANSPARENCIA}/{caminho}",
                                parametros)
        except Exception as erro:  # noqa: BLE001
            print(f"   ✗ falhou: {str(erro)[:160]}\n")
            problemas += 1
            continue

        if isinstance(dados, dict):
            dados = [dados]
        if not dados:
            print("   ⚠ respondeu VAZIA. É o modo de falha da armadilha 12:\n"
                  "     rota documentada, resposta oca. Confira os filtros\n"
                  "     obrigatórios antes de escrever coletor.\n")
            problemas += 1
            continue

        campos = achatar(dados[0])
        print(f"   ✓ {len(dados)} item(ns), {len(campos)} campo(s)")
        for campo, tipo in sorted(campos.items()):
            print(f"       {campo:<52} {tipo}")

        achados = pessoais(campos)
        if achados and agregada:
            print("   ⚠ PARE: campos de pessoa numa rota que eu esperava "
                  "agregada:")
            for campo in achados:
                print(f"       {campo}")
            problemas += 1
        elif achados:
            print(f"   · traz pessoa ({', '.join(achados)}) — é agente "
                  "público no exercício do cargo; decida se entra")
        print()

        if args.salvar:
            destino = RAIZ / "dados" / "bruto" / "portal"
            destino.mkdir(parents=True, exist_ok=True)
            nome = caminho.replace("/", "_")
            (destino / f"{nome}.json").write_text(
                json.dumps(dados[:3], ensure_ascii=False, indent=2),
                encoding="utf-8")

    print("=" * 66)
    if problemas:
        print(f"{problemas} rota(s) com problema. NÃO escreva coletor para "
              "elas antes de resolver.")
    else:
        print("Todas responderam. Mande esta saída — os coletores saem dela.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
