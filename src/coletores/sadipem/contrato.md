# Contrato da API SADIPEM (Tesouro Nacional)

## 1. Visão Geral
- **Provedor**: Secretaria do Tesouro Nacional
- **Base URL**: `https://apidatalake.tesouro.gov.br/ords/cdwhprd/sadipem/tt`
- **Autenticação**: Pública.
- **Limite de Taxa**: 1 req/s.

---

## 2. Endpoints

### 2.1. Pedidos de Verificação de Limites (PVL) — `/pvl`
- Parâmetros: `uf` (str), `offset` (int).
- Campos: `id_pleito`, `cod_ibge`, `uf`, `tipo_interessado`, `interessado`, `num_pvl`, `status`, `tipo_operacao`, `finalidade`, `credor`, `valor`, `pvl_contradado_credor` / `pvl_contratado_credor`, `data_protocolo`, `data_status`.
