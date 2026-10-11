# Deploy PersonalAICoach to VPS (root@193.168.196.12)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RemoteDir = "/opt/personal-ai-coach"
$SshTarget = "root@193.168.196.12"
$Identity = "$env:USERPROFILE\.ssh\alexklyvibe"
$SshOpts = @("-i", $Identity, "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=accept-new")

Write-Host "==> SSH check $SshTarget"
ssh @SshOpts $SshTarget "uname -a && docker --version"

Write-Host "==> Inventory existing containers"
ssh @SshOpts $SshTarget "docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' || true"

Write-Host "==> Stop/remove old PredictiveSalesAnalytics stacks (best-effort)"
ssh @SshOpts $SshTarget @"
set -e
for d in /opt/AI-PredictiveSalesAnalytics /opt/ai-predictivesalesanalytics /root/AI-PredictiveSalesAnalytics /var/www/salesanalytics; do
  if [ -f \"\$d/compose.yaml\" ] || [ -f \"\$d/docker-compose.yml\" ]; then
    echo \"Stopping \$d\"
    (cd \"\$d\" && (docker compose down -v || docker-compose down -v || true))
  fi
done
# Named containers / projects that look like sales analytics
docker ps -a --format '{{.Names}}' | grep -Ei 'sales|predictive|prophet' | while read n; do
  echo \"Removing container \$n\"
  docker rm -f \"\$n\" || true
done
docker volume ls --format '{{.Name}}' | grep -Ei 'sales|predictive' | while read v; do
  echo \"Removing volume \$v\"
  docker volume rm \"\$v\" || true
done
mkdir -p $RemoteDir
"@

Write-Host "==> Sync project (excluding .venv, .git, caches)"
$Tar = Join-Path $env:TEMP "personal-ai-coach-deploy.tgz"
if (Test-Path $Tar) { Remove-Item $Tar -Force }
Push-Location $ProjectRoot
try {
  tar -czf $Tar `
    --exclude=.venv `
    --exclude=.git `
    --exclude=__pycache__ `
    --exclude=.pytest_cache `
    --exclude=.ruff_cache `
    --exclude=agent-tools `
    --exclude=*.pyc `
    .
} finally {
  Pop-Location
}

scp @SshOpts $Tar "${SshTarget}:/tmp/personal-ai-coach-deploy.tgz"
ssh @SshOpts $SshTarget @"
set -e
mkdir -p $RemoteDir
cd $RemoteDir
tar -xzf /tmp/personal-ai-coach-deploy.tgz
rm -f /tmp/personal-ai-coach-deploy.tgz
# Ensure .env exists
test -f .env || cp env.example .env
# Prod mongo host for compose.prod
grep -q '^MONGO_HOST=' .env && sed -i 's/^MONGO_HOST=.*/MONGO_HOST=mongo/' .env || echo 'MONGO_HOST=mongo' >> .env
grep -q '^APP_ENV=' .env && sed -i 's/^APP_ENV=.*/APP_ENV=production/' .env || echo 'APP_ENV=production' >> .env
grep -q '^PUBLIC_BASE_URL=' .env && sed -i 's|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=https://aicareercoach.alexklyvibe.ru|' .env || echo 'PUBLIC_BASE_URL=https://aicareercoach.alexklyvibe.ru' >> .env
grep -q '^API_BASE_URL=' .env && sed -i 's|^API_BASE_URL=.*|API_BASE_URL=http://api:8000|' .env || echo 'API_BASE_URL=http://api:8000' >> .env
docker compose -f compose.prod.yaml up -d --build
docker compose -f compose.prod.yaml ps
"@

Write-Host "==> Health via localhost on VPS"
ssh @SshOpts $SshTarget "sleep 8; curl -fsS http://127.0.0.1:8000/health || curl -fsS https://127.0.0.1/health -k || true"
Write-Host "==> Done. Public: https://aicareercoach.alexklyvibe.ru/"
