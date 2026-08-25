# 05 — API

FastAPI em `src/api/servidor.py`. Base: `http://127.0.0.1:8000`.
Documentação interativa automática em `/docs`.

Toda rota lê apenas views DuckDB. Nenhuma chama fonte externa — exceto
`/api/malha/{uf}`, que baixa a malha do IBGE na primeira vez e a guarda em
disco.

## Configuração

| Rota | Devolve |
|---|---|
| `GET /api/config` | o que está configurado — a chave volta **mascarada** |
| `POST /api/config/chave-portal` | grava a chave da CGU no `.env` e testa |

```json
POST /api/config/chave-portal
{"chave": "a1b2c3…"}        ← aceita também o bloco de exemplo da CGU inteiro
→ {"salva": true, "mascara": "a1b2…8f90", "validada": true,
   "mensagem": "chave aceita pelo Portal da Transparência."}
```

Segredo não trafega de volta por rota de leitura: `GET /api/config` devolve
`a1b2…8f90`, o bastante para conferir e insuficiente para usar. A chave também
não aparece no log — só a máscara.

A gravação preserva comentários, ordem e as outras variáveis do `.env`, e usa
arquivo temporário + rename atômico. A chave passa a valer sem reiniciar: o
`.env`, o módulo de configuração e as sessões HTTP de **todas as threads** são
atualizados (as sessões por contador de geração, já que a coleta roda noutra
thread).

## Atualização de dados (botão Atualizar do painel)

| Rota | Devolve |
|---|---|
| `GET /api/coleta/catalogo` | as seis fontes, com rótulo e cadência |
| `POST /api/coleta` | inicia a coleta em segundo plano; **202** com a tarefa |
| `GET /api/coleta` | a tarefa corrente (ou a última): etapas, progresso e log |
| `GET /api/coleta/{id}` | uma tarefa específica |

```json
POST /api/coleta
{"fontes": ["camara", "senado"], "ano": null,
 "nivel": "estado", "uf": null}
```

O POST volta na hora — a coleta continua numa thread. O painel consulta
`GET /api/coleta` a cada 2 segundos e mostra etapa por etapa mais o log ao vivo.

**Uma tarefa por vez.** Pedir uma segunda enquanto a primeira roda devolve
**409**, não uma fila silenciosa: duas varreduras disputariam o mesmo freio de
rede e reescreveriam a mesma partição.

Sem `ano`, cada fonte usa o seu: Câmara e Senado o ano corrente, SICONFI e
emendas o exercício fechado, TSE as duas últimas eleições.

## Meta

| Rota | Devolve |
|---|---|
| `GET /api/saude` | situação e última leitura de cada fonte |
| `GET /api/anos` | anos com dado no armazém, mais recente primeiro |
| `GET /api/metricas` | catálogo de indicadores |
| `POST /api/recarregar` | recria as views (use depois de uma coleta nova) |

## Mapa

**`GET /api/mapa?ano=2024[&uf=SP][&metrica=despesa_per_capita]`**

Sem `uf`, devolve as 27 UFs. Com `uf`, os municípios daquele estado.
Métricas: `despesa_per_capita` (padrão), `despesa_total`, `populacao`.

```json
{
  "nivel": "estado", "uf": null, "ano": 2024,
  "metrica": "despesa_per_capita",
  "total_entes": 27, "entes_com_dado": 27,
  "entes": [
    {"cod_ibge": "35", "nome": "São Paulo", "sigla_uf": "SP",
     "despesa_total": 3.0e10, "populacao": 4.4e7,
     "despesa_per_capita": 681.8}
  ]
}
```

`total_entes` e `entes_com_dado` existem para o rodapé do mapa poder dizer "2
de 27 UFs com dados" em vez de fingir cobertura completa.

**`GET /api/malha/{escopo}`** — GeoJSON. `escopo` = `brasil` ou a sigla da UF.

**`GET /api/ranking?ano=&metrica=&nivel=&uf=&ordem=&limite=`**

**`GET /api/financas/{cod_ibge}?ano=`** — despesa por função do ente.

## Políticos

| Rota | Devolve |
|---|---|
| `GET /api/politicos/resumo?uf=` | quantos existem por cargo |
| `GET /api/politicos?uf=&cargo=&partido=&busca=&limite=` | lista |
| `GET /api/politicos/{sk}/gastos?ano=` | cota parlamentar por mês |

## Projetos de lei

**`GET /api/proposicoes/situacoes`** e **`GET /api/proposicoes/tipos`**

Os valores que EXISTEM no acervo, com a contagem de cada um. O filtro do
painel é montado a partir daqui, em vez de uma lista fixa que envelhece quando
a Câmara cria uma situação nova. Proposição sem situação não vira opção.

**`GET /api/proposicoes?ano=&tipo=&situacao=&autor=&busca=&de=&ate=&limite=`**

`situacao` é comparada por igualdade exata — os valores vêm do endpoint acima,
então não há motivo para busca parcial.

`de` e `ate` no formato `AAAA-MM-DD`, aplicados sobre `data_apresentacao` — a
data em que o fato aconteceu, nunca a data em que o pipeline soube dele.

**`GET /api/proposicoes/{casa}/{id_proposicao}`**

```json
{
  "proposicao": {"identificador": "PL 1/2024", "nome_autor": "...", "...": "..."},
  "tramitacoes": [{"seq_tramitacao": "1", "data_hora": "...", "orgao": "CCJ"}],
  "votacoes": [{"id_votacao": "V1", "sim": 300, "nao": 120, "abstencao": 5}]
}
```

**`GET /api/votacoes/{casa}/{id_votacao}/votos?voto=&partido=&uf=`**

Voto nominal, parlamentar por parlamentar — o produto do painel.

```json
{
  "placar": {"sim": 300, "nao": 120, "abstencao": 5, "total": 425},
  "votos": [{"nome_politico": "...", "sigla_partido": "...",
             "sigla_uf": "SP", "voto": "Sim"}]
}
```

## Convenções

- **Nulo é nulo.** `NaN` e infinito viram `null` no JSON; o painel os desenha
  como "sem dado". Nunca zero.
- **Erro de bind recria as views e repete uma vez.** Coletou dado com a API já
  no ar? A rota se recupera sozinha, sem reiniciar o processo.
- **Rotas de leitura são `GET` e não têm efeito colateral.** A única exceção é
  `POST /api/recarregar`.

## Estáticos

O diretório `publico/` é servido na raiz (`/`). Em produção local, a API e o
painel são o mesmo processo na mesma porta — sem CORS, sem proxy.
