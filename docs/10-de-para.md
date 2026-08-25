# 10 — De-para TSE → IBGE

O ponto que liga as duas metades do painel. Sem ele, o projeto sabe que o
município 3550308 gastou R$ X e sabe que Fulano é prefeito da unidade
eleitoral 71072 — e não consegue dizer que são a mesma cidade.

## Por que não é só um JOIN por nome

O TSE e o IBGE escrevem o mesmo município de formas diferentes, e a diferença
segue padrões:

| IBGE | TSE | Natureza |
|---|---|---|
| Sant'Ana do Livramento | SANTANA DO LIVRAMENTO | apóstrofo |
| Espigão D'Oeste | ESPIGAO DO OESTE | apóstrofo virou preposição |
| Biritiba-Mirim | BIRITIBA MIRIM | hífen |
| Passa-Vinte | PASSA VINTE | hífen (no sentido inverso) |
| Mogi Mirim | MOJI MIRIM | **grafia oficial divergente** |
| Campo Grande (RN) | AUGUSTO SEVERO | **município renomeado** |

As quatro primeiras cedem a normalização. As duas últimas não cedem a regra
nenhuma — e é justamente por isso que existe uma tabela de exceções escrita à
mão em vez de um algoritmo mais esperto.

## Duas chaves, não uma

`src/nucleo/nomes.py`:

- **estrita** — minúsculas, sem acento, pontuação virando espaço.
  `Biritiba-Mirim` → `biritiba mirim`
- **frouxa** — tira também espaços e preposições (de/da/do/das/dos/e/d).
  `Espigão D'Oeste` e `ESPIGAO DO OESTE` → ambos `espigaooeste`

A frouxa é agressiva de propósito. Por isso só entra depois da estrita, e
sempre **dentro da mesma UF** — sem isso, "Bonito" (que existe em MS, PA, PE e
BA) viraria uma loteria.

## Os quatro passos

Do mais seguro ao menos, e **cada linha guarda por qual passo entrou**:

| Método | O que é |
|---|---|
| `excecao` | grafia que nenhuma regra concilia, escrita à mão |
| `exata` | mesma UF, chave estrita idêntica |
| `frouxa` | mesma UF, chave sem pontuação nem preposições |
| `aproximada` | similaridade ≥ 0,88 **e** vantagem ≥ 0,04 sobre o segundo |
| `pendente` | nada disso — fica sem código IBGE |
| `ambiguo` | dois municípios da mesma UF disputam o nome |

Guardar o método importa: um casamento aproximado que ninguém consegue
auditar depois é pior do que um município sem prefeito na tela.

A similaridade é distância de Levenshtein normalizada, escrita à mão em vez de
`difflib.SequenceMatcher` — o SequenceMatcher trabalha por blocos comuns e é
generoso demais com nomes curtos.

## Ambiguidade nunca vira chute

Se dois candidatos ficam a menos de 0,04 um do outro, a linha fica pendente.
A conta é simples: um prefeito faltando é uma lacuna visível, que alguém
conserta. Um prefeito atribuído à cidade errada é um erro invisível, que
alguém repete.

## Ver e resolver pendências

```bash
python -m src.scripts.coletar --pendencias
```

ou `GET /api/de-para/pendencias`, que também lista os casamentos
`aproximada` para conferência.

Para resolver: acrescente a grafia em `EXCECOES`, no topo de
`src/coletores/de_para.py`, e rode o TSE de novo.

```python
EXCECOES = {
    ("RN", "AUGUSTO SEVERO"): "Campo Grande",
    ...
}
```

A chave é `(UF, nome como o TSE escreve, normalizado em maiúsculas)`; o valor é
o nome como o IBGE escreve.

## Efeito no modelo de dados

A chave primária de `mandato` usa **`cod_ue`**, o identificador que a fonte
realmente fornece — não `cod_ibge`. `cod_ibge` é preenchido pelo de-para e pode
ficar nulo.

Isso é deliberado: chave primária não pode depender de um casamento que talvez
não aconteça. Se dependesse, um município que não casou hoje e casa amanhã
mudaria de `sk` e viraria linha duplicada.

## O que isso destrava

`GET /api/ente/{cod_ibge}` devolve, numa chamada: o ente, quanto gasta e em
quê, os indicadores, quem é o prefeito, quem é o governador da UF, quem é o
presidente, e quantos vereadores tem.

No painel, é o que acontece ao clicar num município depois de entrar num
estado.
