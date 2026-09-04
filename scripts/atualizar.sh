#!/usr/bin/env bash
# ==============================================================================
# Script Rápido para Atualizar o Painel no Cloud Run
# ==============================================================================
set -e

AMBIENTE="${1:-uat}"
REGIAO="${2:-southamerica-east1}"
SERVICO="painel-transparencia-${AMBIENTE}"

echo "🔄 Puxando atualizações do Git..."
git pull

echo "🚀 Atualizando $SERVICO no Cloud Run (Região: $REGIAO)..."
gcloud run deploy "$SERVICO" \
    --source . \
    --region "$REGIAO" \
    --quiet

echo "✅ Atualização concluída com sucesso!"
gcloud run services describe "$SERVICO" --region "$REGIAO" --format="value(status.url)"
