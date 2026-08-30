# 04 — Coletores

Um arquivo por fonte, em `src/coletores/`. Todos idempotentes: podem ser
re-rodados a qualquer momento sem duplicar nada.

## Anatomia

```python
from ..nucleo import armazem, config, controle, rede
from ..nucleo.registro import obter as obter_log

log = obter_log("coletores.minhafonte")
FONTE = "minhafonte"

def coletar_algo(ano: int) -> int:
    corpo = rede.buscar(FONTE, f"{config.MINHA_URL}/recurso", {"ano": ano})

    linhas = [{
        "cod_ibge": item["codigo"],       # campos da PK declarados no esquema
        "ano": ano,
        "valor": float(item["valor"]),
        "data_referencia": f"{ano}-12-31",
    } for item in corpo["dados"]]

    armazem.mesclar("minha_tabela", linhas, FONTE)
    controle.gravar_marca(FONTE, f"algo_{ano}", ano, len(linhas))
    return len(linhas)

def executar(anos=None) -> None:
    for ano in anos or [date.today().year]:
        try:
            coletar_algo(ano)
        except Exception as erro:
            log.error("%s %d falhou: %s", FONTE, ano, erro)
```

O coletor **não** calcula `sk`, `_hash_registro` nem carimbos de tempo —
`armazem.mesclar()` faz isso a partir do que `esquema.py` declara.

## Para adicionar uma fonte nova

1. **Declare a tabela** em `src/nucleo/esquema.py`: `campos_pk`, `particoes` e
   o contrato `colunas` (usado para a view vazia tipada).
2. **Registre a URL base** em `src/nucleo/config.py` e o freio em
   `INTERVALO_REQUISICOES`.
3. **Escreva o coletor** no formato acima.
4. **Registre no CLI**: adicione o nome em `ORDEM` e no `_modulo()` de
   `src/scripts/coletar.py`.
5. **Se o painel precisa do dado**, crie a view derivada em
   `src/api/vistas.py` e a rota em `servidor.py`.

## Regras que valem para todos

**Falhe alto no schema, baixo na rede.** PK ausente estoura na hora (bug de
código). Fonte fora do ar é registrada, marcada como erro no controle de
ingestão e o pipeline segue — uma fonte cair não pode derrubar as outras cinco.

**Nunca invente número.** Valor ausente vai como `None`, não como zero. O
painel desenha cinza e diz quantos entes têm dado. Zero é uma afirmação sobre
o mundo; cinza é uma afirmação sobre o acervo.

**Prefira o lote à API** para carga histórica. CSV diário é auditável,
reexecutável e não depende de milhares de chamadas.

**Respeite o freio.** `rede.buscar()` já aplica o intervalo por fonte. Não
contorne com `requests` direto.

## Marca-d'água

```python
controle.gravar_marca(FONTE, "recurso", marca, linhas, situacao="ok")
ultima = controle.ler_marca(FONTE, "recurso")
```

Alimenta a aba **Fontes** do painel — a resposta honesta para "de quando é
esse número?".

## O que existe hoje

| Coletor | Tabelas que escreve |
|---|---|
| `ibge` | `dim_ente`, `dim_metrica`, `indicador_ente`, malhas GeoJSON |
| `siconfi` | `financas_ente` |
| `camara` | `dim_politico`, `proposicao`, `tramitacao`, `votacao`, `voto`, `despesa_parlamentar` |
| `senado` | `dim_politico`, `votacao`, `voto` |
| `tse` | `dim_politico`, `dim_partido`, `dim_cargo`, `mandato` |
| `portal_transparencia` | `emenda_parlamentar` |

## Varredura em massa

Coletar 27 UFs é um laço simples. Coletar 5.570 municípios exige três coisas,
todas em `siconfi.varrer()`:

**1. Retomada por ente.** Cada ente tentado vira uma linha em
`_ctl/coleta_ente` com situação `ok`, `vazio` ou `erro`. A execução seguinte
pula os resolvidos e **repete os que deram erro** — que é exatamente o caso de
queda de conexão no meio da varredura. Você pode fechar a janela no minuto 12
de 20 e retomar no dia seguinte.

```bash
python -m src.scripts.coletar siconfi --nivel municipio --ano 2024
python -m src.scripts.coletar siconfi --nivel municipio --uf BA   # só uma UF
python -m src.scripts.coletar siconfi --refazer-vazios --ano 2024 # tenta os sem dado
```

**2. Gravação em lotes.** Todos os municípios de um ano caem na mesma partição
(`ano=`, `esfera=municipio`) e cada merge reescreve o arquivo inteiro. Gravar
de 500 em 500 troca 5.570 reescritas por 12. Lote menor = mais resiliente e
mais lento; lote maior = o contrário.

**3. Freio global, não por thread.** Os trabalhadores existem para esconder a
latência (~1s por resposta), não para pedir mais rápido. `nucleo.rede` reserva
o próximo horário de saída dentro de uma trava e dorme fora dela, então seis
threads produzem requisições **espaçadas**, não uma rajada. Aumentar
`--trabalhadores` sem aumentar `--intervalo` não acelera nada — só enfileira.

Padrões: 6 trabalhadores, 0,15 s de espaçamento → ~6,7 req/s → 5.570 municípios
em 15 a 25 minutos na primeira vez.

Muitos municípios pequenos simplesmente não publicam o DCA. Eles são marcados
`vazio` e não são tentados de novo, a menos que você peça com
`--refazer-vazios`. Ver a contagem:

```bash
python -m src.scripts.coletar --situacao --ano 2024
```

## Linha de comando

```bash
python -m src.scripts.coletar --situacao
python -m src.scripts.coletar ibge --sem-malhas
python -m src.scripts.coletar siconfi --ano 2024 --limite 5   # teste rápido
python -m src.scripts.coletar camara --anos 2023 2024 2026
python -m src.scripts.coletar tse --anos 2022 2024
python -m src.scripts.coletar --tudo
```

## Ler arquivo: use `nucleo.tabela`

Nenhum coletor deve chamar `pd.read_csv` direto. `nucleo.tabela` centraliza o
que três coletores faziam cada um do seu jeito:

```python
from ..nucleo import tabela

df = tabela.ler(conteudo, origem=url)              # CSV, JSON, XLSX ou ZIP
df = tabela.de_zip(conteudo, origem=url,
                   ignorar=("BRASIL",))            # vários CSVs num ZIP
faltando = tabela.colunas_faltando(df, ("valor",), url)
```

O que ele resolve, e que se perdia quando cada um fazia o seu:

- **UTF-8 antes de latin-1** — ver armadilha 2w, a mais silenciosa da lista
- reconhece ZIP, XLSX, JSON e **HTML** (página de erro servida como sucesso)
- quando falha, o erro traz tamanho, primeiros bytes e o que foi tentado
- resposta de zero byte é erro, nunca tabela vazia

Um leitor que não sabe dizer por que não leu transfere para uma pessoa o
trabalho que o código tinha condição de fazer.
