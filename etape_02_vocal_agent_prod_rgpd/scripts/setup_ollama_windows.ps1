# setup_ollama_windows.ps1 — Configure Ollama sur Windows pour le projet Traiteur Dupont
#
# Prérequis : PowerShell 5.1+ ou PowerShell 7+
# Usage :
#   .\scripts\setup_ollama_windows.ps1
#   .\scripts\setup_ollama_windows.ps1 -Model llama3.1:8b
#
# Ce script :
#   1. Installe Ollama (via winget ou téléchargement direct)
#   2. Configure OLLAMA_HOST pour accepter les connexions Docker/WSL
#   3. Télécharge le modèle LLM
#   4. Affiche la configuration .env à utiliser

param(
    [string]$Model = "qwen2.5:7b"
)

$ErrorActionPreference = "Stop"
$OllamaUrl = "http://localhost:11434"

Write-Host "=== Setup Ollama Windows — Traiteur Dupont Étape 02 ===" -ForegroundColor Cyan
Write-Host "Modèle cible : $Model"
Write-Host ""

# ── 1. Installation d'Ollama ──────────────────────────────────────────────────
$ollamaInstalled = Get-Command ollama -ErrorAction SilentlyContinue

if (-not $ollamaInstalled) {
    Write-Host "[1/4] Ollama absent — installation..." -ForegroundColor Yellow

    # Tentative via winget (Windows 11 / Windows 10 récent)
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host "  Installation via winget..."
        winget install -e --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
    } else {
        # Téléchargement direct de l'installeur
        $installer = "$env:TEMP\OllamaSetup.exe"
        Write-Host "  Téléchargement de l'installeur Ollama..."
        Invoke-WebRequest -Uri "https://ollama.com/download/windows" -OutFile $installer
        Write-Host "  Lancement de l'installeur (suivez les étapes)..."
        Start-Process -FilePath $installer -Wait
        Remove-Item $installer -ErrorAction SilentlyContinue
    }

    # Rafraîchir le PATH pour trouver ollama
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH", "User")
} else {
    $version = & ollama --version 2>&1
    Write-Host "[1/4] Ollama déjà installé : $version" -ForegroundColor Green
}

# ── 2. Configuration OLLAMA_HOST ──────────────────────────────────────────────
# Par défaut Ollama écoute sur 127.0.0.1 → inaccessible depuis Docker/WSL.
# OLLAMA_HOST=0.0.0.0 permet à Docker Desktop et WSL2 de s'y connecter.
Write-Host ""
Write-Host "[2/4] Configuration OLLAMA_HOST=0.0.0.0 (accès depuis Docker/WSL)..." -ForegroundColor Yellow

$currentHost = [System.Environment]::GetEnvironmentVariable("OLLAMA_HOST", "User")
if ($currentHost -ne "0.0.0.0") {
    [System.Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0", "User")
    $env:OLLAMA_HOST = "0.0.0.0"
    Write-Host "  OLLAMA_HOST défini à 0.0.0.0 (variable d'environnement utilisateur)."
    Write-Host "  Un redémarrage d'Ollama est nécessaire pour prendre effet."
} else {
    Write-Host "  OLLAMA_HOST déjà configuré à 0.0.0.0." -ForegroundColor Green
}

# ── 3. Démarrage d'Ollama ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/4] Vérification du service Ollama..." -ForegroundColor Yellow

$ollamaRunning = $false
try {
    $response = Invoke-WebRequest -Uri "$OllamaUrl/api/tags" -UseBasicParsing -TimeoutSec 3
    $ollamaRunning = $response.StatusCode -eq 200
} catch {}

if (-not $ollamaRunning) {
    Write-Host "  Démarrage d'Ollama en arrière-plan..."
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
    # Attente jusqu'à 60s
    for ($i = 1; $i -le 12; $i++) {
        try {
            Invoke-WebRequest -Uri "$OllamaUrl/api/tags" -UseBasicParsing -TimeoutSec 3 | Out-Null
            Write-Host "  Ollama prêt." -ForegroundColor Green
            $ollamaRunning = $true
            break
        } catch {
            Write-Host "  Attente Ollama... ($i/12)"
            Start-Sleep -Seconds 5
        }
    }
}

if (-not $ollamaRunning) {
    Write-Host "ERREUR : Ollama n'a pas démarré. Lancez 'ollama serve' manuellement." -ForegroundColor Red
    exit 1
}

# ── 4. Téléchargement du modèle ───────────────────────────────────────────────
Write-Host ""
Write-Host "[4/4] Pull du modèle '$Model' (peut prendre plusieurs minutes)..." -ForegroundColor Yellow
& ollama pull $Model

# ── Vérification ──────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Modèles disponibles ===" -ForegroundColor Cyan
& ollama list

Write-Host ""
Write-Host "=== Configuration .env recommandée ===" -ForegroundColor Cyan
Write-Host "LLM_PROVIDER=local_ollama"
Write-Host "LLM_MODEL=$Model"
Write-Host "OLLAMA_BASE_URL=http://host.docker.internal:11434"
Write-Host ""
Write-Host "Docker Desktop expose automatiquement 'host.docker.internal' → votre machine Windows."
Write-Host ""
Write-Host "=== Setup terminé. Lancez ensuite : docker compose up ===" -ForegroundColor Green
