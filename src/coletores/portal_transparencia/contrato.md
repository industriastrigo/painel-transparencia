# Contrato da API do Portal da Transparência (CGU)

## 1. Visão Geral
- **Provedor**: Controladoria-Geral da União (CGU)
- **Base URL**: `https://api.portaldatransparencia.gov.br/api-de-dados`
- **Autenticação**: Cabeçalho `chave-api-dados`.
- **Obtenção da Chave**: Gratuita em `portaldatransparencia.gov.br/api-de-dados/cadastrar-email`.

---

## 2. Endpoints

### 2.1. Emendas Parlamentares — `/emendas`
- Parâmetros: `ano` (int), `pagina` (int).
- Campos: `codigoEmenda`, `tipoEmenda`, `nomeAutor`, `numeroEmenda`, `funcao`, `subfuncao`, `valorEmpenhado`, `valorLiquidado`, `valorPago`, `localidadeDoGasto`.

### 2.2. Cartões Corporativos (CPGF) — `/cartoes`
- Parâmetros: `mesExtratoInicio` (MM/AAAA), `mesExtratoFim` (MM/AAAA), `pagina` (int).
- Campos: `unidadeGestora` (`codigo`, `nome`), `portador` (`nome`, `codigoFormatado`), `favorecido` (`nome`, `codigoFormatado`), `tipoCartao`, `dataTransacao`, `valorTransacao`.
