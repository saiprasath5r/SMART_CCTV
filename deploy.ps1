# ─────────────────────────────────────────────────────────────────────────────
# SMART CCTV — Full Deployment Script
# Deploys backend to Google Cloud Run + frontend to Firebase Hosting
#
# Usage: .\deploy.ps1
# Prerequisites: gcloud CLI, firebase CLI, Docker Desktop must be installed
# ─────────────────────────────────────────────────────────────────────────────

param(
    [string]$ProjectId = "",         # Firebase/GCP Project ID (prompted if empty)
    [string]$Region = "us-central1", # Cloud Run region
    [string]$ServiceName = "smart-cctv-backend", # Cloud Run service name
    [string]$ImageName = "smart-cctv"            # Docker image name
)

$ErrorActionPreference = "Stop"

Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     SMART CCTV — Firebase + Cloud Run Deployment Script     ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── Step 0: Get Project ID ────────────────────────────────────────────────────
if ($ProjectId -eq "") {
    $ProjectId = Read-Host "Enter your Google Cloud / Firebase Project ID"
}
Write-Host "✓ Project ID: $ProjectId" -ForegroundColor Green

# ── Step 1: Ensure .firebaserc is set ────────────────────────────────────────
Write-Host "`n[1/7] Configuring Firebase project..." -ForegroundColor Yellow
$firerbc = @{default = $ProjectId} | ConvertTo-Json
$firerbc | Set-Content ".firebaserc"
Write-Host "✓ .firebaserc written" -ForegroundColor Green

# ── Step 2: Enable required GCP APIs ─────────────────────────────────────────
Write-Host "`n[2/7] Enabling Cloud Run & Artifact Registry APIs..." -ForegroundColor Yellow
gcloud services enable run.googleapis.com artifactregistry.googleapis.com --project $ProjectId
Write-Host "✓ APIs enabled" -ForegroundColor Green

# ── Step 3: Create Artifact Registry repository (if not exists) ───────────────
Write-Host "`n[3/7] Setting up Artifact Registry..." -ForegroundColor Yellow
$repoExists = gcloud artifacts repositories list --project $ProjectId --location $Region --format "value(name)" 2>$null | Select-String "smart-cctv-repo"
if (-not $repoExists) {
    gcloud artifacts repositories create smart-cctv-repo `
        --repository-format=docker `
        --location=$Region `
        --project=$ProjectId
    Write-Host "✓ Repository created" -ForegroundColor Green
} else {
    Write-Host "✓ Repository already exists" -ForegroundColor Green
}

# ── Step 4: Build & Push Docker Image ────────────────────────────────────────
Write-Host "`n[4/7] Building & pushing Docker image..." -ForegroundColor Yellow
$imageUrl = "$Region-docker.pkg.dev/$ProjectId/smart-cctv-repo/${ImageName}:latest"
Write-Host "  Image: $imageUrl" -ForegroundColor Gray

gcloud auth configure-docker "$Region-docker.pkg.dev" --quiet
docker build -t $imageUrl .
docker push $imageUrl
Write-Host "✓ Docker image pushed" -ForegroundColor Green

# ── Step 5: Deploy to Cloud Run ───────────────────────────────────────────────
Write-Host "`n[5/7] Deploying to Cloud Run..." -ForegroundColor Yellow

# Optionally load .env to pass as Cloud Run secrets
$envArgs = @()
if (Test-Path ".env") {
    Write-Host "  Loading env vars from .env..." -ForegroundColor Gray
    Get-Content ".env" | Where-Object { $_ -match "^[A-Z_]+=.+" -and $_ -notmatch "^#" } | ForEach-Object {
        $envArgs += "--set-env-vars"
        $envArgs += $_
    }
}

gcloud run deploy $ServiceName `
    --image $imageUrl `
    --platform managed `
    --region $Region `
    --allow-unauthenticated `
    --port 8080 `
    --memory 2Gi `
    --cpu 1 `
    --min-instances 0 `
    --max-instances 3 `
    --timeout 300 `
    --project $ProjectId `
    @envArgs

# Get the deployed Cloud Run URL
$backendUrl = gcloud run services describe $ServiceName --region $Region --project $ProjectId --format "value(status.url)"
Write-Host "✓ Cloud Run deployed at: $backendUrl" -ForegroundColor Green

# ── Step 6: Inject Backend URL into static frontend ──────────────────────────
Write-Host "`n[6/7] Injecting backend URL into frontend..." -ForegroundColor Yellow

# Patch public/index.html — replace %%BACKEND_URL%% placeholder
(Get-Content "public\index.html") -replace "%%BACKEND_URL%%", $backendUrl | Set-Content "public\index.html"

# Update firebase.json rewrites with actual Cloud Run service info
Write-Host "✓ Backend URL injected: $backendUrl" -ForegroundColor Green

# ── Step 7: Deploy Firebase Hosting ──────────────────────────────────────────
Write-Host "`n[7/7] Deploying to Firebase Hosting..." -ForegroundColor Yellow
firebase deploy --only hosting --project $ProjectId

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                  ✅ DEPLOYMENT COMPLETE                     ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  🔥 Firebase Hosting:  https://$ProjectId.web.app" -ForegroundColor Cyan
Write-Host "  ☁️  Cloud Run Backend: $backendUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "  ⚠️  Don't forget to set your environment variables in Cloud Run:" -ForegroundColor Yellow
Write-Host "     GEMINI_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, etc." -ForegroundColor Yellow
Write-Host "  → https://console.cloud.google.com/run/detail/$Region/$ServiceName/edit?project=$ProjectId" -ForegroundColor Gray
