"""Sonda da API Pública do DataJud — roda ANTES de existir coletor.

Este arquivo existe por causa da armadilha 12 do `docs/08-armadilhas.md`:
documentação não é contrato. A API da Câmara documenta rotas que devolvem
lista vazia; o RREO custou oito horas de carga porque o formato real não era
o formato que eu supus. A regra que saiu daí é que **nenhum coletor novo
entra sem uma resposta real conferida** — e eu não consigo conferir esta
daqui, porque o ambiente onde escrevo o código não alcança o host do CNJ.

Então a ordem se inverte: primeiro esta sonda roda na SUA máquina e mostra o
que a fonte devolve de verdade; o coletor vem depois, escrito contra o que
ela imprimiu.

Ela também é um **freio de privacidade**. A API Pública deveria devolver só
metadado processual — classe, assunto, órgão julgador, movimentos. O acervo
restrito (`view-processos-sigilo-*`, que este projeto NÃO acessa) é que tem
nome, CPF, endereço e nome da genitora, no modelo MNI. Se algum campo de
pessoa vazar para a resposta pública, a sonda GRITA e o coletor não deve ser
escrito antes de resolver isso.

Uso:
    python scripts/conferir_datajud.py            # TJSP, amostra pequena
    python scripts/conferir_datajud.py --tribunal tjmg --salvar
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib import error, request

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

BASE = "https://api-publica.datajud.cnj.jus.br"

# Chave PÚBLICA, publicada pelo próprio CNJ na wiki do DataJud. Não é
# segredo — ao contrário da chave do Portal da Transparência, que mora no
# .env e nunca entra no repositório. Se esta parar de funcionar, o CNJ a
# rotacionou: pegue a nova na wiki, não peça a ninguém.
CHAVE_PUBLICA = ("cDZHYzlZa0JadVREZDJCendQbXY6"
                 "SkJlTzNjLV9TRENyQk1RdnFKZGRQdw==")

# Nomes que NÃO podem aparecer numa resposta pública. Se aparecerem, ou o
# CNJ mudou o que expõe, ou apontamos para o índice errado.
CAMPOS_DE_PESSOA = (
    "nomeParte", "numeroDocumentoPrincipal", "cpf", "cnpj", "documento",
    "nomeGenitora", "nomeGenitor", "dataNascimento", "endereco",
    "pessoa", "parte", "polo", "advogado", "login", "email",
)


def pedir(caminho: str, corpo: dict, tempo: int = 60) -> dict:
    req = request.Request(
        f"{BASE}/{caminho}",
        data=json.dumps(corpo).encode("utf-8"),
        headers={"Authorization": f"APIKey {CHAVE_PUBLICA}",
                 "Content-Type": "application/json"},
        method="POST")
    with request.urlopen(req, timeout=tempo) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def achatar(objeto, prefixo: str = "") -> dict[str, str]:
    """Todo caminho de campo → tipo. É o mapa que o coletor vai precisar."""
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


def conferir_privacidade(campos) -> list[str]:
    achados = []
    for campo in campos:
        curto = campo.split(".")[-1].replace("[]", "").lower()
        for proibido in CAMPOS_DE_PESSOA:
            if curto == proibido.lower():
                achados.append(campo)
    return achados


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tribunal", default="tjsp",
                    help="alias do tribunal, ex.: tjsp, tjmg, trf1, tst")
    ap.add_argument("--salvar", action="store_true",
                    help="grava a resposta crua em dados/bruto/datajud/")
    args = ap.parse_args()

    caminho = f"api_publica_{args.tribunal}/_search"
    print(f"→ POST {BASE}/{caminho}\n")

    # ---- 1. a resposta existe e tem que forma? --------------------------
    try:
        bruto = pedir(caminho, {"size": 2, "query": {"match_all": {}},
                                "sort": [{"@timestamp": {"order": "asc"}}]})
    except error.HTTPError as erro:
        print(f"✗ HTTP {erro.code}: {erro.read()[:400].decode(errors='replace')}")
        return 1
    except Exception as erro:  # noqa: BLE001
        print(f"✗ não deu para falar com a fonte: {erro}")
        return 1

    total = bruto.get("hits", {}).get("total", {})
    linhas = bruto.get("hits", {}).get("hits", [])
    print(f"total de processos no índice: {total.get('value')} "
          f"({total.get('relation')})")
    print(f"registros nesta amostra: {len(linhas)}")
    if not linhas:
        print("\n✗ A rota respondeu mas veio VAZIA. É exatamente o modo de\n"
              "  falha da armadilha 12: rota documentada, resposta oca.\n"
              "  NÃO escreva coletor. Confira o alias do tribunal e a chave.")
        return 1

    fonte = linhas[0].get("_source", {})
    campos = achatar(fonte)

    print(f"\n--- CAMPOS REAIS ({len(campos)}) ---")
    for campo, tipo in sorted(campos.items()):
        print(f"  {campo:<58} {tipo}")

    # ---- 2. o freio de privacidade -------------------------------------
    print("\n--- PRIVACIDADE ---")
    achados = conferir_privacidade(campos)
    if achados:
        print("  ⚠ PARE. Campos de pessoa na resposta pública:")
        for campo in achados:
            print(f"      {campo}")
        print("  Um painel público não republica isso. Resolva antes de\n"
              "  escrever qualquer coletor.")
    else:
        print("  ✓ nenhum campo de pessoa na amostra — só metadado "
              "processual, como a Portaria 160/2020 promete")
    print(f"  nivelSigilo desta amostra: {fonte.get('nivelSigilo')!r}")

    # ---- 3. o search_after realmente pagina? ---------------------------
    print("\n--- PAGINAÇÃO (search_after) ---")
    marca = linhas[-1].get("sort")
    if not marca:
        print("  ⚠ a resposta não trouxe `sort`; sem ele não há paginação —\n"
              "    e sem paginação um coletor lê só as 10 primeiras linhas")
    else:
        try:
            pagina2 = pedir(caminho, {
                "size": 2, "query": {"match_all": {}},
                "sort": [{"@timestamp": {"order": "asc"}}],
                "search_after": marca})
            ids1 = [h.get("_id") for h in linhas]
            ids2 = [h.get("_id") for h in pagina2["hits"]["hits"]]
            if ids2 and not set(ids1) & set(ids2):
                print(f"  ✓ avançou de verdade: {ids1} → {ids2}")
            else:
                print(f"  ⚠ a segunda página repetiu ou veio vazia: {ids2}")
        except Exception as erro:  # noqa: BLE001
            print(f"  ✗ falhou: {erro}")

    # ---- 4. agregação: é assim que o painel vai usar -------------------
    # O painel não quer processo a processo — quer contagem por órgão e por
    # classe, para cruzar com o CUSTO do Judiciário que já temos no acervo.
    print("\n--- AGREGAÇÃO (o formato que o painel realmente quer) ---")
    try:
        agregado = pedir(caminho, {
            "size": 0,
            "aggs": {"por_classe": {"terms": {"field": "classe.codigo",
                                              "size": 5}}}})
        baldes = agregado.get("aggregations", {}).get("por_classe", {}) \
                         .get("buckets", [])
        if baldes:
            print("  ✓ agregação funciona — 5 maiores classes:")
            for balde in baldes:
                print(f"      classe {balde['key']:<8} {balde['doc_count']:>12,} processos")
        else:
            print("  ⚠ agregação respondeu sem baldes; o painel teria de\n"
                  "    baixar processo a processo, o que muda tudo")
    except Exception as erro:  # noqa: BLE001
        print(f"  ✗ agregação falhou: {erro}")

    if args.salvar:
        destino = RAIZ / "dados" / "bruto" / "datajud"
        destino.mkdir(parents=True, exist_ok=True)
        arquivo = destino / f"amostra_{args.tribunal}.json"
        arquivo.write_text(json.dumps(bruto, ensure_ascii=False, indent=2),
                           encoding="utf-8")
        print(f"\nresposta crua guardada em {arquivo}")

    print("\nMande esta saída inteira. O coletor sai dela, não do PDF.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
