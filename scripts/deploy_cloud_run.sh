#!/usr/bin/env bash
# ==============================================================================
# Script de Deploy Automático para o Google Cloud Run (UAT / PRD) - Google Cloud Shell
# ==============================================================================
# Uso:
#   ./scripts/deploy_cloud_run.sh [uat|prd] [SEU_PROJETO_ID] [REGIAO]
#
# Exemplo:
#   ./scripts/deploy_cloud_run.sh uat
#   ./scripts/deploy_cloud_run.sh prd meu-projeto-gcp southamerica-east1
# ==============================================================================

set -e

AMBIENTE="${1:-uat}"
PROJETO_ID="${2:-}"
REGIAO="${3:-southamerica-east1}"

GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-}"
GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET:-}"
SESSION_SECRET_KEY="${SESSION_SECRET_KEY:-$(openssl rand -hex 24 2>/dev/null || echo "chave-secreta-sessao-$(date +%s)")}"
EMAILS_PERMITIDOS="${EMAILS_PERMITIDOS:-}"

# 1. Identifica o Projeto GCP
if [ -z "$PROJETO_ID" ]; then
    echo "🔍 Buscando projeto GCP ativo no gcloud..."
    PROJETO_ID=$(gcloud config get-value project 2>/dev/null || true)
    if [ -z "$PROJETO_ID" ]; then
        echo "❌ ERRO: Nenhum projeto GCP configurado."
        echo "Execute primeiro: gcloud config set project SEU_PROJECT_ID"
        exit 1
    fi
fi

SERVICO_NOME="painel-transparencia-${AMBIENTE}"

echo "======================================================================"
echo "🚀 INICIANDO DEPLOY NO GOOGLE CLOUD RUN"
echo "  📦 Serviço:     $SERVICO_NOME"
echo "  🌍 Ambiente:    $AMBIENTE"
echo "  🏢 Projeto GCP: $PROJETO_ID"
echo "  📍 Região:      $REGIAO"
echo "======================================================================"

# 2. Habilita APIs necessárias no Google Cloud
echo ""
echo "[1/3] ⚙️  Verificando e ativando APIs necessárias (Cloud Run, Cloud Build, Artifact Registry)..."
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    --project "$PROJETO_ID"

# 3. Executa o build e deploy direto via Cloud Build e Cloud Run
echo ""
echo "[2/3] 🐳 Construindo imagem Docker e enviando para o Cloud Run..."
gcloud run deploy "$SERVICO_NOME" \
    --source . \
    --project "$PROJETO_ID" \
    --region "$REGIAO" \
    --platform managed \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 3 \
    --set-env-vars="AMB=${AMBIENTE},EXIGE_AUTH=1,HTTPS_ONLY=1,PERMITIR_SEMEADURA=false,GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID},GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET},SESSION_SECRET_KEY=${SESSION_SECRET_KEY},EMAILS_PERMITIDOS=${EMAILS_PERMITIDOS}"

# 4. Obtém a URL do serviço e configura a BASE_URL
echo ""
echo "[3/3] 🔗 Obtendo URL pública e atualizando BASE_URL..."
URL_SERVICO=$(gcloud run services describe "$SERVICO_NOME" --project "$PROJETO_ID" --region "$REGIAO" --format="value(status.url)")

# Atualiza a BASE_URL com a URL pública final
gcloud run services update "$SERVICO_NOME" \
    --project "$PROJETO_ID" \
    --region "$REGIAO" \
    --update-env-vars="BASE_URL=${URL_SERVICO}" \
    --quiet

echo ""
echo "======================================================================"
echo "🎉 DEPLOY CONCLUÍDO COM SUCESSO!"
echo "🌐 URL Pública do Painel: $URL_SERVICO"
echo "======================================================================"
echo ""
echo "📌 PASSO FINAL OBRIGATÓRIO (Google OAuth):"
echo "1. Abra o Google Cloud Console: https://console.cloud.google.com/apis/credentials?project=$PROJETO_ID"
echo "2. Edite o OAuth 2.0 Client ID (${GOOGLE_CLIENT_ID:0:20}...)"
echo "3. Em 'URIs de redirecionamento autorizados', adicione exatamente:"
echo "   👉 ${URL_SERVICO}/auth/callback"
echo "4. Salve e teste o login acessando: $URL_SERVICO"
echo "======================================================================"
