# ============================================================
#  SmartHR — Push to GitHub (run this once)
#  Edit YOUR_GITHUB_USERNAME and YOUR_GITHUB_TOKEN below
# ============================================================

$GITHUB_USERNAME = "YOUR_GITHUB_USERNAME"   # <-- change this
$GITHUB_TOKEN    = "YOUR_GITHUB_TOKEN"       # <-- paste your token here (ghp_xxx...)
$REPO_NAME       = "smarthr-attendance"      # <-- your repo name on GitHub
$COMMIT_MSG      = "SmartHR Attendance System - Initial commit"

# Build the authenticated remote URL
$REMOTE_URL = "https://${GITHUB_USERNAME}:${GITHUB_TOKEN}@github.com/${GITHUB_USERNAME}/${REPO_NAME}.git"

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  SmartHR — Pushing to GitHub" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1 — Set identity
Write-Host "[1/6] Setting Git identity..." -ForegroundColor Yellow
git config --global user.name  $GITHUB_USERNAME
git config --global user.email "${GITHUB_USERNAME}@users.noreply.github.com"

# Step 2 — Init (safe if already done)
Write-Host "[2/6] Initialising Git..." -ForegroundColor Yellow
git init
git branch -M main

# Step 3 — Suppress line-ending warnings
git config core.autocrlf true

# Step 4 — Stage all files
Write-Host "[3/6] Staging all files..." -ForegroundColor Yellow
git add .

# Step 5 — Commit
Write-Host "[4/6] Committing..." -ForegroundColor Yellow
git commit -m $COMMIT_MSG

# Step 6 — Set remote (remove old one if exists)
Write-Host "[5/6] Setting remote origin..." -ForegroundColor Yellow
git remote remove origin 2>$null
git remote add origin $REMOTE_URL

# Step 7 — Push
Write-Host "[6/6] Pushing to GitHub..." -ForegroundColor Yellow
git push -u origin main --force

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "  DONE! Check your repo:" -ForegroundColor Green
Write-Host "  https://github.com/$GITHUB_USERNAME/$REPO_NAME" -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
