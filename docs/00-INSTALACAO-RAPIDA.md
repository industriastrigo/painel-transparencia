# 00 — Instalação rápida

## Requisito único

Python 3.10 ou superior, com "Add Python to PATH" marcado na instalação.
Confira abrindo o Prompt de Comando e digitando `python --version`.

## Windows

1. Dê dois cliques em **INSTALAR.bat**.
   Ele cria `.venv`, instala as dependências, copia `.env.example` para `.env`
   e faz a primeira carga (IBGE + SICONFI das 27 UFs). Leva alguns minutos —
   a maior parte é o download das malhas geográficas.
2. Dê dois cliques em **ABRIR PAINEL.bat**.
   O navegador abre em `http://127.0.0.1:8000`.

## Linux / macOS

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m src.scripts.instalar --carga
python -m src.scripts.painel
```

## O que a primeira carga traz

A fatia mínima que prova o pipeline ponta a ponta: **mapa Brasil → UF →
município colorido por despesa total per capita**. Três fontes, um número, um
mapa funcionando.

| Fonte | O que entra |
|---|---|
| IBGE Localidades | país, 27 UFs, 5.570 municípios |
| IBGE Malhas | GeoJSON do Brasil por UF |
| IBGE SIDRA | população e PIB |
| SICONFI | despesa por função das 27 UFs |

O módulo legislativo (deputados, projetos, votos) é quase um projeto
independente do módulo geográfico e entra depois:

```bash
python -m src.scripts.coletar camara --anos 2024 2026
```

## Emendas parlamentares (opcional)

Exigem chave gratuita da CGU:

1. Cadastre o e-mail em
   `portaldatransparencia.gov.br/api-de-dados/cadastrar-email`
2. Abra o arquivo `.env` e preencha `CHAVE_PORTAL_TRANSPARENCIA=`
3. `python -m src.scripts.coletar portal_transparencia --anos 2024`

Sem a chave o coletor não quebra o pipeline: registra a pendência e o painel
mostra "sem dados" — nunca um número inventado.

## Se algo der errado

| Sintoma | Causa provável |
|---|---|
| `python não é reconhecido` | Python fora do PATH — reinstale marcando a opção |
| Painel abre vazio | Nenhuma carga feita ainda; rode `INSTALAR.bat` |
| Estados todos cinzas | SICONFI não coletado; veja a aba Fontes |
| `Falha definitiva em ...` | Fonte fora do ar ou IP freado; rode de novo mais tarde |
| `[Errno 13]` ao subir | Porta reservada pelo Windows; o script troca sozinho — use o endereço impresso na tela (ver `07-operacao.md`) |

O log completo de cada execução fica em `logs/painel-AAAA-MM-DD.log`.
