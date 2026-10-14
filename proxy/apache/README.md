# Existing Apache server: ai.sfs.at

Apache terminates HTTPS for `ai.sfs.at` and forwards the whole application to
Open WebUI at `127.0.0.1:3000`. The Docker services do not need certificates.
This configuration assumes Apache runs directly on the **same host** as Docker,
Apache is version 2.4.47 or newer, and its TLS library supports TLS 1.3.
For Apache in another container or on another machine, the upstream address
must be changed; do not expose port 3000 publicly as a workaround.

Keep existing cloud virtual hosts enabled. Add this as a separate named virtual
host; no existing cloud configuration or certificate needs to be replaced.

## 1. Update the application configuration

From the repository directory:

```bash
git pull
nano .env
```

Set exactly one `COMPOSE_FILE` entry, replacing any Caddy setting:

```dotenv
BIND_ADDRESS=127.0.0.1
COMPOSE_FILE=compose.yaml:compose.apache.yaml
```

If bundled Caddy was previously started, stop it before applying this setup:

```bash
docker compose -f compose.yaml -f compose.proxy.yaml stop proxy
```

That command is only needed if Caddy exists. Then start the base services with
the Apache URL overlay enabled by `.env`:

```bash
docker compose config --quiet
docker compose up -d --build
curl --fail http://127.0.0.1:3000/health
```

## 2. DNS and Apache modules

Point the DNS A record for `ai.sfs.at` to this server. Any AAAA record must also
reach it. TCP ports 80 and 443 must reach Apache. Enable required modules:

```bash
apache2ctl -v
sudo a2enmod ssl proxy proxy_http headers rewrite setenvif
```

Before creating a new site, check for an existing `ai.sfs.at` virtual host with
`sudo apache2ctl -S`. Avoid duplicate named virtual hosts for this domain.

## 3. Obtain a certificate if needed

If you already have a valid certificate covering `ai.sfs.at`, skip issuance
and update the two certificate paths in `ai.sfs.at.conf` to match it. An existing
certificate for another hostname does not automatically cover this one;
a wildcard for `*.sfs.at` would cover `ai.sfs.at`.

Otherwise, install Certbot if it is not already available, enable the HTTP-only
bootstrap site, and issue a certificate without stopping Apache:

```bash
sudo apt install certbot
sudo mkdir -p /var/www/memory-ai-acme/.well-known/acme-challenge
sudo install -m 644 proxy/apache/ai.sfs.at-http.conf /etc/apache2/sites-available/memory-ai-http.conf
sudo a2ensite memory-ai-http
sudo apache2ctl configtest
sudo systemctl reload apache2
sudo certbot certonly --webroot -w /var/www/memory-ai-acme -d ai.sfs.at --cert-name ai.sfs.at
```

Certbot may ask for a contact email and acceptance of the CA terms. Enable the
HTTPS file only after the certificate files exist; Apache refuses a configuration
that references missing certificates.

## 4. Enable HTTPS

From the repository directory:

```bash
sudo install -m 644 proxy/apache/ai.sfs.at.conf /etc/apache2/sites-available/memory-ai.conf
```

If you used the HTTP bootstrap above, disable that site:

```bash
sudo a2dissite memory-ai-http
```

Then enable the complete site and validate before reloading:

```bash
sudo a2ensite memory-ai
sudo apache2ctl configtest
sudo systemctl reload apache2
curl --fail --show-error https://ai.sfs.at/health
```

Reload only if the configuration test reports `Syntax OK`. Open
<https://ai.sfs.at>, sign in and send a streaming chat message to check HTTP,
SSE and WebSocket behavior end to end. Only the Apache virtual host needs the
certificate; Open WebUI, LiteLLM, Qdrant and PostgreSQL stay internal.

## 5. Certificate renewal

If you issued the webroot certificate above, check the existing Certbot renewal
timer and add a deploy hook so Apache reloads renewed certificates:

```bash
systemctl status certbot.timer
sudo mkdir -p /etc/letsencrypt/renewal-hooks/deploy
sudo tee /etc/letsencrypt/renewal-hooks/deploy/memory-ai-reload-apache.sh > /dev/null <<'HOOK'
#!/bin/sh
set -eu
/usr/sbin/apache2ctl configtest
/usr/bin/systemctl reload apache2
HOOK
sudo chmod 755 /etc/letsencrypt/renewal-hooks/deploy/memory-ai-reload-apache.sh
sudo certbot renew --cert-name ai.sfs.at --dry-run
```

If Certbot is already installed through a different method, use its existing
scheduled renewal mechanism rather than adding a second one. If using an
existing certificate, retain its existing renewal process.

## Validation limits

These files have not been loaded into your Apache instance in the authoring
environment. The `configtest`, health check and browser check above are required
on your server. No server, DNS or certificate changes are performed by merely
committing these files to GitHub.

References:

- <https://httpd.apache.org/docs/2.4/mod/mod_proxy.html>
- <https://eff-certbot.readthedocs.io/en/stable/using.html>
