#!/usr/bin/env bash
# ==============================================================================
# Script de Deploy Automático para o Google Cloud Run (UAT / PRD) - Bash
# ==============================================================================
# Uso:
#   ./scripts/deploy_cloud_run.sh uat seu-projeto-gcp [southamerica-east1]
#   ./scripts/deploy_cloud_run.sh prd seu-projeto-gcp [southamerica-east1]
# ==============================================================================

set -e

AMBIENTE="${1:-uat}"
PROJETO_ID="${2:-}"
REGIAO="${3:-southamerica-east1}"

if [ -z "$PROJETO_ID" ]; then
    echo "Buscando projeto GCP configurado no gcloud..."
    PROJETO_ID=$(gcloud config get-value project 2>/dev/null)
    if [ -z "$PROJETO_ID" ]; then
        echo "ERRO: Nenhum projeto GCP informado. Passe o parâmetro ou rode: gcloud config set project SEU_PROJETO"
        exit 1
    fi
fi

SERVICO_NOME="painel-transparencia-${AMBIENTE}"

echo "======================================================================"
echo "Iniciando deploy para Google Cloud Run"
echo "  Serviço:    $SERVICO_NOME"
echo "  Ambiente:   $AMBIENTE"
echo "  Projeto:    $PROJETO_ID"
echo "  Região:     $REGIAO"
echo "======================================================================"

# 1. Habilita APIs necessárias no Google Cloud
echo "[1/3] Verificando e ativando APIs necessárias (Cloud Run, Cloud Build)..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --project "$PROJETO_ID"

# 2. Executa o build e deploy direto via Cloud Build e Cloud Run
echo "[2/3] Construindo imagem Docker e enviando para o Cloud Run..."
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
    --set-env-vars="AMB=$AMBIENTE,EXIGE_AUTH=1,HTTPS_ONLY=1"

# 3. Obtém e exibe a URL final
URL_SERVICO=$(gcloud run services describe "$SERVICO_NOME" --project "$PROJETO_ID" --region "$REGIAO" --format="value(status.url)")

echo "======================================================================"
echo "Deploy concluído com sucesso!"
echo "URL Pública: $URL_SERVICO"
echo "======================================================================"
echo ""
echo "PRÓXIMOS PASSOS OBRIGATÓRIOS:"
echo "1. Configure as variáveis de ambiente de autenticação no Cloud Run:"
echo "   gcloud run services update $SERVICO_NOME --region $REGIAO --update-env-vars GOOGLE_CLIENT_ID='<seu_id>',GOOGLE_CLIENT_SECRET='<seu_secret>',SESSION_SECRET_KEY='<sua_chave>',EMAILS_PERMITIDOS='<email1,email2>',BASE_URL='$URL_SERVICO'"
echo ""
echo "2. No Google Cloud Console (APIs e Serviços > Credenciais):"
echo "   Adicione nas URIs de Redirecionamento autorizadas do seu OAuth Client:"
echo "   $URL_SERVICO/auth/callback"
echo ""
