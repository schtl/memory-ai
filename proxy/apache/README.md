# Apache reverse proxy: configurable domain

Apache on the Docker host terminates HTTPS and proxies to `127.0.0.1:3000`.
Use Apache 2.4.47 or newer with TLS 1.3 support. Keep existing cloud virtual
hosts enabled; this creates a separate named virtual host.

## Configure the domain once

From the repository directory:

```bash
git pull
nano .env
```

Set exactly one `COMPOSE_FILE` entry, replacing any Caddy setting:

```dotenv
PUBLIC_DOMAIN=ai.sfs.at
BIND_ADDRESS=127.0.0.1
COMPOSE_FILE=compose.yaml:compose.apache.yaml
```

The Compose overlay reads `PUBLIC_DOMAIN` for Open WebUI's public HTTPS URL.
Use a literal DNS hostname, without a scheme, port, path or wildcard. Variable
expansion such as `${OTHER_DOMAIN}` is not supported by the generator.

Generate both Apache configurations (Python 3, no third-party packages):

```bash
python3 scripts/generate_apache.py
```

Outputs:

- `generated/apache/memory-ai-http.conf`: HTTP-only certificate bootstrap.
- `generated/apache/memory-ai.conf`: HTTPS proxy, HTTP redirect and ACME renewal.

The generator validates input and preserves Apache's `${APACHE_LOG_DIR}` variable.
It overwrites its generated files when rerun, but never installs Apache files,
issues certificates or reloads services. Generated files are excluded from Git.
The checked-in `ai.sfs.at*.conf` files are static examples; use the generated
files for deployment.

For an existing Let's Encrypt certificate covering the chosen domain, optionally
set its directory name, for example:

```dotenv
APACHE_CERTIFICATE_NAME=sfs.at
```

This produces certificate paths under `/etc/letsencrypt/live/sfs.at/`. Leave it
empty to use the domain as the certificate name. The generator does not inspect
the certificate: it must actually cover `PUBLIC_DOMAIN`. Certificates elsewhere
require adapting the generated certificate paths before installation.

## Start the application

If bundled Caddy was previously started, stop it first:

```bash
docker compose -f compose.yaml -f compose.proxy.yaml stop proxy
```

Skip that command if Caddy does not exist. Then:

```bash
docker compose config --quiet
docker compose up -d --build
curl --fail http://127.0.0.1:3000/health
```

This assumes Apache runs on the **same host** as Docker. If Apache is in a
container or on another machine, `127.0.0.1` is not the Docker host; the upstream
network configuration must be adapted.

## Enable Apache and issue a certificate

Point the domain's A record to this server. Any AAAA record must also reach it.
TCP ports 80/443 must reach Apache. Confirm no duplicate virtual host exists for
this domain with `sudo apache2ctl -S`.

```bash
sudo a2enmod ssl proxy proxy_http headers rewrite setenvif
sudo mkdir -p /var/www/memory-ai-acme/.well-known/acme-challenge
```

If an appropriate certificate already exists, skip bootstrap and issuance below
and proceed to **Enable HTTPS**. Otherwise:

```bash
sudo apt install certbot
sudo install -m 644 generated/apache/memory-ai-http.conf /etc/apache2/sites-available/memory-ai-http.conf
sudo a2ensite memory-ai-http
sudo apache2ctl configtest
sudo systemctl reload apache2
```

Reload only after `Syntax OK`. Issue the certificate without stopping Apache
(replace `ai.sfs.at` with your configured domain if different):

```bash
sudo certbot certonly --webroot -w /var/www/memory-ai-acme -d ai.sfs.at --cert-name ai.sfs.at
```

Certbot may ask for a contact email and CA terms acceptance. The generated TLS
file must not be enabled before its certificate files exist.

## Enable HTTPS

```bash
sudo install -m 644 generated/apache/memory-ai.conf /etc/apache2/sites-available/memory-ai.conf
```

If the HTTP-only bootstrap site was enabled, disable it:

```bash
sudo a2dissite memory-ai-http
```

Then:

```bash
sudo a2ensite memory-ai
sudo apache2ctl configtest
sudo systemctl reload apache2
curl --fail --show-error https://ai.sfs.at/health
```

Reload only after `Syntax OK`. Open the configured HTTPS domain, sign in and send
a streaming chat message. Only Apache needs the certificate; Docker services
stay behind it. Existing cloud virtual hosts retain their own configuration.

## Renewal

For the webroot certificate above, use the existing Certbot renewal scheduler
and add a deploy hook if Apache is not already reloaded after renewal:

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

For Certbot installed through another method, retain its existing renewal
mechanism. Reusing an existing certificate also means retaining its renewal
process. Change the domain in the renewal check if you configured another one.

## Change the domain later

Edit `PUBLIC_DOMAIN` in `.env`, regenerate, obtain a certificate for the new
hostname (or configure a matching existing certificate), reinstall the generated
HTTPS file, validate and reload Apache, then run `docker compose up -d`.
DNS and certificate issuance are not automated by the generator. Reinstalling
the generated virtual host replaces its previous hostname; existing certificate
renewal entries are not removed automatically.

## Tests

```bash
python3 -m unittest discover -s tests -p test_apache_generator.py -v
```

These dependency-free tests cover rendering, certificate paths, hostname and
path validation, quoted settings, duplicate settings, regeneration and rejection
without overwriting existing output. They also run as part of the Docker suite.
Apache `configtest` and the HTTPS/browser checks must still be run on your server.

References:

- <https://httpd.apache.org/docs/2.4/mod/mod_proxy.html>
- <https://eff-certbot.readthedocs.io/en/stable/using.html>
