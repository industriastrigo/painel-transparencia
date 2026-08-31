# Contrato da API da Câmara dos Deputados

## 1. Visão Geral
- **Provedor**: Câmara dos Deputados (Coordenação de Dados Abertos)
- **API REST**: `https://dadosabertos.camara.leg.br/api/v2`
- **Arquivos em Lote (CSV)**: `https://dadosabertos.camara.leg.br/arquivos/`
- **Taxa de Atualização**: Diária.

---

## 2. Endpoints e Arquivos em Lote

### 2.1. Deputados — `/deputados`
- Paginação via link `rel="next"`.
- Campos: `id`, `nome`, `nomeEleitoral`, `siglaPartido`, `siglaUf`, `idLegislatura`, `urlFoto`.

### 2.2. Proposições — `proposicoes-{ano}.csv` & `/proposicoes/{id}/tramitacoes`
- Campos: `id`, `siglaTipo`, `numero`, `ano`, `ementa`, `dataApresentacao`, `ultimoStatus_descricaoSituacao`, `ultimoStatus_descricaoTramitacao`.
- Autores: `proposicoesAutores-{ano}.csv`.

### 2.3. Votações e Votos — `votacoes-{ano}.csv`, `votacoesVotos-{ano}.csv`, `votacoesOrientacoes-{ano}.csv`
- Votos Nominais: Extraídos via arquivo em lote por integridade histórica (a rota REST `/votacoes/{id}/votos` retorna vazio para votações recentes).

### 2.4. Cota Parlamentar (CEAP) — `despesasParlamentares-{ano}.csv` / `Ano-{ano}.csv.zip`
- Campos: `ideDocumento`, `numParcela`, `numRessarcimento`, `txNomeParlamentar`, `txtDescricao`, `txtFornecedor`, `txtCNPJCPF`, `vlrDocumento`, `vlrLiquido`, `datEmissao`, `urlDocumento`.
