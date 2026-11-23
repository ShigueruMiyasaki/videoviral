#!/bin/bash
# Sobe o VideoViral nesta máquina. Rode na pasta do projeto, como root ou com sudo.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
    echo "Instalando Docker..."
    curl -fsSL https://get.docker.com | sh
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "O plugin docker compose não está disponível."
    exit 1
fi

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Criei .env a partir de .env.example. Coloque as chaves de API nele."
fi

python_set() {
    local key="$1"
    local value="$2"
    if grep -q "^${key}=" .env; then
        local current
        current="$(grep "^${key}=" .env | head -n 1 | cut -d= -f2-)"
        if [ -z "$current" ]; then
            sed -i "s|^${key}=.*|${key}=${value}|" .env
        fi
    else
        echo "${key}=${value}" >> .env
    fi
}

if ! grep -q '^DASHBOARD_PASSWORD=.\+' .env; then
    PASS="$(openssl rand -base64 18 | tr -d '\n')"
    python_set DASHBOARD_PASSWORD "$PASS"
    echo ""
    echo "Senha nova do painel (usuário admin): ${PASS}"
    echo "Ela ficou gravada em .env. Guarde agora."
    echo ""
fi

python_set DASHBOARD_USER "admin"

DOMAIN="$(grep '^VIDEOVIRAL_DOMAIN=' .env | head -n 1 | cut -d= -f2- || true)"
if [ -n "$DOMAIN" ]; then
    EMAIL="${ACME_EMAIL:-admin@${DOMAIN}}"
    cat > deploy/Caddyfile <<EOF
{
	email ${EMAIL}
}

${DOMAIN} {
	reverse_proxy api:8000
}
EOF
    echo "HTTPS em https://${DOMAIN}"
else
    cat > deploy/Caddyfile <<'EOF'
:80 {
	reverse_proxy api:8000
}
EOF
    echo "Sem domínio: o painel responde em http://IP-DA-VPS"
fi

if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw allow 80/tcp
    ufw allow 443/tcp
fi

docker compose -f docker-compose.prod.yml up -d --build

echo ""
echo "Pronto. Saúde do serviço:"
docker compose -f docker-compose.prod.yml ps
echo "Teste interno: docker compose -f docker-compose.prod.yml exec api python -c \"import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read())\""
