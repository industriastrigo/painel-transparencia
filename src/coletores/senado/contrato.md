# Contrato da API do Senado Federal

## 1. Visão Geral
- **Provedor**: Senado Federal (Secretaria de Tecnologia da Informação)
- **Base URL**: `https://legis.senado.leg.br/dadosabertos`
- **Autenticação**: Pública.

---

## 2. Endpoints

### 2.1. Senadores em Exercício — `/senador/lista/atual.json`
- Árvore: `ListaParlamentarEmExercicio` -> `Parlamentares` -> `Parlamentar`.
- Campos: `IdentificacaoParlamentar` (`CodigoParlamentar`, `NomeCompletoParlamentar`, `SiglaPartidoParlamentar`, `UfParlamentar`, `UrlFotoParlamentar`).

### 2.2. Votações por Matéria — `/materia/votacoes/{codigo}.json`
- Árvore: `VotacaoMateria` -> `Materia` -> `Votacoes` -> `Votacao`.
- Votos Nominais: `Votos` -> `VotoParlamentar` (`CodigoParlamentar`, `Voto`, `SiglaPartido`, `SiglaUF`).
