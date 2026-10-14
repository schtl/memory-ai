#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
umask 077
if [[ -e .env ]]; then
  echo '.env already exists; leaving it unchanged.'
  exit 0
fi
command -v openssl >/dev/null
cp .env.example .env
for key in POSTGRES_PASSWORD WEBUI_SECRET_KEY MEMORY_API_KEY LITELLM_MASTER_KEY LITELLM_SALT_KEY ADMIN_PASSWORD; do
  value=$(openssl rand -hex 32)
  if [[ "$key" == LITELLM_* ]]; then value="sk-$value"; fi
  sed -i "s/^${key}=.*/${key}=${value}/" .env
done
mkdir -p data
chmod 700 data
echo '.env created. Set ADMIN_EMAIL, CLOUD_MODEL, CLOUD_API_BASE and CLOUD_API_KEY.'
