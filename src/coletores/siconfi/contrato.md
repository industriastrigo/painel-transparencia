# Contrato da API SICONFI (Tesouro Nacional)

## 1. Visão Geral
- **Provedor**: Secretaria do Tesouro Nacional (STN) / Ministério da Fazenda
- **Base URL**: `https://apidatalake.tesouro.gov.br/ords/siconfi/tt/`
- **Autenticação**: Pública, sem necessidade de chave de API.
- **Limite de Taxa (Rate Limit)**: 1 requisição por segundo (documentado oficialmente).

---

## 2. Endpoints e Parâmetros

### 2.1. DCA (Declaração de Contas Anuais) — `/dca`
- **Finalidade**: Despesas anuais por natureza e receitas orçamentárias brutas realizadas.
- **Parâmetros**:
  - `an_exercicio` (int): Exercício financeiro (ex: 2024, 2025).
  - `no_anexo` (str):
    - `DCA-Anexo I-D`: Despesas por função/natureza.
    - `DCA-Anexo I-C`: Receitas orçamentárias realizadas.
  - `id_ente` (str/int): Código IBGE do ente (2 dígitos para UF, 7 dígitos para município, 0/1 para União).
- **Campos Principais de Retorno**:
  - `cod_conta` (str): Código da conta contábil.
  - `conta` (str): Descrição por extenso da conta.
  - `coluna` (str): Estágio da despesa/receita (ex: "Despesas Empenhadas", "Receitas Brutas Realizadas").
  - `valor` (float): Valor apurado no exercício.

### 2.2. RREO (Relatório Resumido da Execução Orçamentária) — `/rreo`
- **Finalidade**: Execução bimestral da despesa por Função e Subfunção de Governo (Portaria MOG 42/1999).
- **Parâmetros**:
  - `an_exercicio` (int): Ano de referência.
  - `in_periodicidade` (str): `"B"` (Bimestral - obrigatório).
  - `nr_periodo` (int): Bimestre (1 a 6).
  - `co_tipo_demonstrativo` (str): `"RREO"`.
  - `no_anexo` (str): `"RREO-Anexo 02"`.
  - `id_ente` (str/int): Código IBGE do ente.
- **Regras Contábeis**:
  - Coluna de interesse: `ATÉ O BIMESTRE (B)` (acumulada no exercício).
  - Bloco `exceto_intra` vs `intra`: Distinguido pelo sufixo do `cod_conta`.

### 2.3. RGF (Relatório de Gestão Fiscal) — `/rgf`
- **Finalidade**: Despesa com pessoal sobre a RCL (limites da LRF) e Dívida Consolidada Líquida (saldo).
- **Parâmetros**:
  - `an_exercicio` (int): Ano de referência.
  - `in_periodicidade` (str): `"Q"` (Quadrimestral) ou `"S"` (Semestral).
  - `nr_periodo` (int): Quadrimestre (1 a 3) ou Semestre (1 a 2).
  - `co_tipo_demonstrativo` (str): `"RGF"`.
  - `no_anexo` (str): `"RGF-Anexo 01"` (Pessoal) ou `"RGF-Anexo 02"` (Dívida).
  - `co_poder` (str): `"E"` (Executivo) ou `"L"` (Legislativo).
  - `id_ente` (str/int): Código IBGE do ente.

### 2.4. Extrato de Entregas — `/extrato_entregas`
- **Finalidade**: Verificar se o ente homologou e entregou os relatórios fiscais do exercício.
- **Parâmetros**:
  - `id_ente` (str): Código IBGE.
  - `an_referencia` (int): Exercício.
