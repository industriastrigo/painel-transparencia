# Contrato de Dados do Tribunal Superior Eleitoral (TSE)

## 1. Visão Geral
- **Provedor**: Tribunal Superior Eleitoral (TSE) - Portal de Dados Abertos
- **Origem dos Arquivos**: `https://cdn.tse.jus.br/estatistica/sead/odsele`
- **Formato**: ZIP contendo arquivos CSV por UF e nacional.

---

## 2. Conjuntos de Dados

### 2.1. Consulta de Candidaturas e Eleitos — `consulta_cand_{ano}.zip`
- Filtro de Eleitos: `DS_SIT_TOT_TURNO` em `{"ELEITO", "ELEITO POR QP", "ELEITO POR MÉDIA", "MÉDIA"}`.
- Campos: `SQ_CANDIDATO`, `NM_CANDIDATO`, `NM_URNA_CANDIDATO`, `SG_PARTIDO`, `SG_UF`, `SG_UE`, `NM_UE`, `CD_CARGO`, `DS_GENERO`, `DS_COR_RACA`, `DS_GRAU_INSTRUCAO`, `DS_OCUPACAO`, `DT_NASCIMENTO`.

### 2.2. Declaração de Bens — `bem_candidato_{ano}.zip`
- Campos: `SQ_CANDIDATO`, `DS_TIPO_BEM_CANDIDATO`, `DS_BEM_CANDIDATO`, `VR_BEM_CANDIDATO`.
