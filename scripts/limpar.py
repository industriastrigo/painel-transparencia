"""Faxina da pasta do projeto: tira arquivo sem uso e log velho.

**Não apaga nada sem `--apagar`.** Rodar sem argumento só mostra o que sairia.

A regra, decidida pelo Johnny em 28/08/2026:

    dado coletado NUNCA sai. Sai arquivo sem uso e log.

Isso vale inclusive para `_to_delete/`, apesar do nome. Aquela pasta guarda
parquets que foram substituídos por mudança de chave — mas parquet com
linha dentro é dado, e dado não se apaga por estar numa pasta com nome feio.
Fui eu que dei aquele nome, e ele mente: hoje o `_to_delete/sprint1` é a
ÚNICA cópia de 52.847 linhas de despesa por função e 28.263 de indicadores
fiscais, porque a recoleta que deveria substituí-lo nunca rodou.

Deste diretório, então, saem só duas coisas:
  - parquets de 0 byte, que não guardam nada;
  - `zips/`, que são pacotes de entrega, não acervo.

O que este script NUNCA toca, em nenhum modo:
    .env  .git  .venv  dados/  referencias  src  publico  docs  testes
    scripts  e qualquer .parquet com conteúdo

Uso:
    python scripts/limpar.py               # só mostra
    python scripts/limpar.py --apagar      # apaga
    python scripts/limpar.py --manter-logs # poupa os logs
"""
from __future__ import annotations

import argparse
import os
import shutil
import time
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Caminhos intocáveis. A checagem é por prefixo, então nada abaixo deles
# entra em nenhuma lista, por erro de glob ou por descuido meu.
# `dados` inteiro está aqui: acervo, arquivo bruto e marcas de controle.
INTOCAVEIS = (
    ".env", ".git", ".venv", "dados", "referencias",
    "src", "publico", "docs", "testes", "scripts",
)

# Cache SEMPRE pode sair, mesmo dentro de pasta intocável: `src/` é
# protegido porque guarda código, não porque guarda `__pycache__`. Sem esta
# exceção o script protegeria justamente o lixo que veio limpar.
CACHES = ("__pycache__", ".pytest_cache")

# Pastas grandes que a varredura não precisa percorrer. Sem podar, um
# `rglob` a partir da raiz anda por dezenas de milhares de parquets à
# procura de pasta de cache que nunca esteve lá — minutos, num disco de rede.
PODAR = {".venv", ".git", "dados", "_to_delete", "node_modules"}

# Scripts de rascunho que sobraram de investigações já encerradas. Não são
# importados por nada, não têm teste, e o que eles investigavam virou teste
# de verdade em `testes/`.
RASCUNHOS = ("validar.py", "tempCodeRunnerFile.bat")


def protegido(caminho: Path) -> bool:
    try:
        relativo = caminho.resolve().relative_to(RAIZ)
    except ValueError:
        return True                      # fora da pasta do projeto: nunca
    if caminho.name in CACHES:
        return False
    # Rede de segurança final: qualquer parquet com conteúdo é dado.
    if caminho.is_file() and caminho.suffix == ".parquet":
        return caminho.stat().st_size > 0
    texto = str(relativo)
    return any(texto == p or texto.startswith(p + os.sep) for p in INTOCAVEIS)


def tamanho(caminho: Path) -> int:
    if caminho.is_file():
        return caminho.stat().st_size
    return sum(f.stat().st_size for f in caminho.rglob("*") if f.is_file())


def humano(n: float) -> str:
    for unidade in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unidade}"
        n /= 1024
    return f"{n:.1f} TB"


# --------------------------------------------------------------- candidatos
def coletar(com_logs: bool) -> tuple[list, list]:
    """Devolve (o que pode sair, o que precisa de atenção)."""
    seguros: list[tuple[Path, str]] = []
    avisos: list[str] = []

    # 1. Cache de Python. Renasce sozinho no próximo import.
    for pasta_atual, subpastas, _ in os.walk(RAIZ):
        subpastas[:] = [s for s in subpastas if s not in PODAR]
        for sub in list(subpastas):
            if sub in CACHES:
                seguros.append((Path(pasta_atual) / sub,
                                "cache do Python, recriado sozinho"))
                subpastas.remove(sub)          # não desce dentro do cache

    # 2. Sobras do DuckDB. Só existem enquanto uma consulta roda; se o painel
    #    estiver aberto AGORA, apagar derruba a consulta. Daí a idade.
    tmp = RAIZ / ".tmp"
    if tmp.is_dir():
        blocos = list(tmp.glob("*.block"))
        recentes = [b for b in blocos if time.time() - b.stat().st_mtime < 3600]
        if recentes:
            avisos.append(
                f".tmp/ tem {len(recentes)} bloco(s) do DuckDB com menos de "
                "uma hora — pode ser consulta em andamento. Feche o painel e "
                "rode de novo. Não incluí.")
        elif blocos:
            seguros.append((tmp, "sobra de consulta do DuckDB, nenhuma recente"))

    # 3. Rascunhos e artefatos de editor.
    for nome in RASCUNHOS:
        caminho = RAIZ / nome
        if caminho.exists():
            seguros.append((caminho, "rascunho sem uso — nada importa daqui"))

    # 4. Pacotes que a conversa entregou e você já descompactou.
    for zipe in RAIZ.glob("*.zip"):
        seguros.append((zipe, "pacote de atualização já aplicado"))

    # 5. Merge interrompido: o armazém escreve `.parquet.tmp` e só depois
    #    renomeia, então um `.tmp` sobrando é metade de arquivo — lixo de
    #    verdade. Mas mora dentro de `dados/`, e a regra é que este script
    #    não entra ali. Então ele apenas AVISA, e quem apaga é você.
    #    (A primeira versão tentava apagar; a proteção de `dados/` barrava
    #    em silêncio e a linha nunca fazia nada. Aviso honesto > código
    #    morto que finge trabalhar.)
    sobras = list((RAIZ / "dados").rglob("*.parquet.tmp"))
    if sobras:
        avisos.append(
            f"{len(sobras)} arquivo(s) `.parquet.tmp` em dados/ — metade de "
            "merge interrompido. É lixo, mas está dentro de dados/ e eu não "
            "entro lá. Apague à mão se quiser:\n"
            + "\n".join(f"       {s.relative_to(RAIZ)}" for s in sobras[:5]))

    # 6. `_to_delete/`: só o que comprovadamente não é dado.
    porao = RAIZ / "_to_delete"
    if porao.is_dir():
        vazios = [p for p in porao.rglob("*.parquet") if p.stat().st_size == 0]
        for vazio in vazios:
            seguros.append((vazio, "parquet de 0 byte — não guarda nada"))

        zips = porao / "zips"
        if zips.is_dir():
            seguros.append((zips, "pacotes de entrega, não é acervo"))

        # Tudo o mais fica, e o script diz quanto e por quê.
        preservados = [p for p in porao.rglob("*.parquet")
                       if p.stat().st_size > 0]
        if preservados:
            volume = sum(p.stat().st_size for p in preservados)
            avisos.append(
                f"_to_delete/ tem {len(preservados)} parquet(s) com conteúdo "
                f"({humano(volume)}). NÃO apago: parquet com linha dentro é "
                "dado, e o nome da pasta não muda isso.\n"
                "     Confira antes de apagar à mão — `_to_delete/sprint1` é "
                "hoje a única cópia da carga do RREO.")

    # 7. Logs. Guarda o de hoje: ele está aberto e sendo escrito.
    if com_logs:
        hoje = date.today().isoformat()
        pasta_logs = RAIZ / "logs"
        for log in list(pasta_logs.glob("*.log")) + list(pasta_logs.glob("*.txt")):
            if log.name == "LEIA-ME.txt":
                continue                          # é documentação, não log
            if hoje in log.name:
                continue                          # o de hoje está em uso
            seguros.append((log, "log de execução antiga"))

    return seguros, avisos


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apagar", action="store_true",
                    help="apaga de verdade; sem isto só mostra")
    ap.add_argument("--manter-logs", action="store_true",
                    help="não mexe nos logs")
    args = ap.parse_args()

    print(f"Pasta: {RAIZ}\n")
    seguros, avisos = coletar(com_logs=not args.manter_logs)

    # Tira duplicatas e aplica a proteção uma primeira vez.
    vistos, limpos = set(), []
    for caminho, motivo in seguros:
        chave = str(caminho.resolve())
        if chave in vistos or protegido(caminho):
            continue
        vistos.add(chave)
        limpos.append((caminho, motivo))

    if avisos:
        print("=" * 68)
        print("FICA — dado, ou coisa que pode estar em uso")
        print("=" * 68)
        for aviso in avisos:
            print(f"  · {aviso}")
        print()

    if not limpos:
        print("Nada a apagar.")
        return 0

    total = 0
    print("=" * 68)
    print("PODE SAIR" if args.apagar else "SAIRIA (rode com --apagar)")
    print("=" * 68)
    for caminho, motivo in limpos:
        bytes_ = tamanho(caminho)
        total += bytes_
        print(f"  {humano(bytes_):>9}  {caminho.relative_to(RAIZ)}")
        print(f"             └─ {motivo}")
    print(f"\n  TOTAL: {humano(total)}")

    if not args.apagar:
        print("\nNada foi apagado. Para apagar de verdade:")
        print("    python scripts/limpar.py --apagar")
        return 0

    print()
    apagados = 0
    for caminho, _ in limpos:
        if protegido(caminho):       # cinto e suspensório: confere de novo
            print(f"  recusado (protegido): {caminho.relative_to(RAIZ)}")
            continue
        try:
            shutil.rmtree(caminho) if caminho.is_dir() else caminho.unlink()
            apagados += 1
        except Exception as erro:  # noqa: BLE001
            print(f"  falhou em {caminho.relative_to(RAIZ)}: {erro}")
    print(f"apagados: {apagados} de {len(limpos)} — {humano(total)} livres")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
