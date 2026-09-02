# ==============================================================================
# Script de Deploy Automático para o Google Cloud Run (UAT / PRD)
# ==============================================================================
# Uso:
#   .\scripts\deploy_cloud_run.ps1 -Ambiente uat -ProjetoId seu-projeto-gcp
#   .\scripts\deploy_cloud_run.ps1 -Ambiente prd -ProjetoId seu-projeto-gcp
# ==============================================================================

param (
    [string]$Ambiente = "uat",
    [string]$ProjetoId = "",
    [string]$Regiao = "southamerica-east1" # São Paulo (ou us-central1)
)

$ErrorActionPreference = "Stop"

if (-not $ProjetoId) {
    Write-Host "Buscando projeto GCP configurado no gcloud..." -ForegroundColor Yellow
    $ProjetoId = (gcloud config get-value project 2>$null).Trim()
    if (-not $ProjetoId) {
        Write-Host "ERRO: Nenhum projeto GCP informado. Passe o parametro -ProjetoId ou rode: gcloud config set project SEU_PROJETO" -ForegroundColor Red
        exit 1
    }
}

$ServicoNome = "painel-transparencia-$Ambiente"
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Iniciando deploy para Google Cloud Run" -ForegroundColor Cyan
Write-Host "  Servico:    $ServicoNome" -ForegroundColor Green
Write-Host "  Ambiente:   $Ambiente" -ForegroundColor Green
Write-Host "  Projeto:    $ProjetoId" -ForegroundColor Green
Write-Host "  Regiao:     $Regiao" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan

# 1. Habilita APIs necessárias no Google Cloud
Write-Host "[1/3] Verificando e ativando APIs necessarias (Cloud Run, Cloud Build)..." -ForegroundColor Yellow
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --project $ProjetoId

# 2. Executa o build e deploy direto via Cloud Build e Cloud Run
Write-Host "[2/3] Construindo imagem Docker e enviando para o Cloud Run..." -ForegroundColor Yellow
gcloud run deploy $ServicoNome `
    --source . `
    --project $ProjetoId `
    --region $Regiao `
    --platform managed `
    --allow-unauthenticated `
    --memory 1Gi `
    --cpu 1 `
    --min-instances 0 `
    --max-instances 3 `
    --set-env-vars="AMB=$Ambiente,EXIGE_AUTH=1,HTTPS_ONLY=1"

# 3. Obtém e exibe a URL final
$UrlServico = (gcloud run services describe $ServicoNome --project $ProjetoId --region $Regiao --format="value(status.url)").Trim()

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Deploy concluido com sucesso!" -ForegroundColor Green
Write-Host "URL Publica: $UrlServico" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "PROXIMOS PASSOS OBRIGATORIOS:" -ForegroundColor Yellow
Write-Host "1. Configure as variaveis de ambiente de autenticacao no Cloud Run:" -ForegroundColor White
Write-Host "   gcloud run services update $ServicoNome --region $Regiao --update-env-vars GOOGLE_CLIENT_ID='<seu_id>',GOOGLE_CLIENT_SECRET='<seu_secret>',SESSION_SECRET_KEY='<sua_chave>',EMAILS_PERMITIDOS='<email1,email2>',BASE_URL='$UrlServico'" -ForegroundColor Cyan
Write-Host ""
Write-Host "2. No Google Cloud Console (APIs e Servicos > Credenciais):" -ForegroundColor White
Write-Host "   Adicione nas URIs de Redirecionamento autorizadas do seu OAuth Client:" -ForegroundColor White
Write-Host "   $UrlServico/auth/callback" -ForegroundColor Cyan
Write-Host ""
