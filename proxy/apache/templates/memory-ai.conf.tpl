# Apache 2.4.47+ on the Docker host. Existing cloud virtual hosts stay separate.
<VirtualHost *:80>
    ServerName {{DOMAIN}}
    DocumentRoot /var/www/memory-ai-acme

    <Directory /var/www/memory-ai-acme>
        Options None
        AllowOverride None
        Require all granted
    </Directory>

    # Keep HTTP-01 validation available for certificate renewal.
    RewriteEngine On
    RewriteCond %{REQUEST_URI} !^/\.well-known/acme-challenge/
    RewriteRule ^ https://{{DOMAIN}}%{REQUEST_URI} [R=301,L]
</VirtualHost>

<VirtualHost *:443>
    ServerName {{DOMAIN}}
    SSLEngine On
    SSLCertificateFile /etc/letsencrypt/live/{{CERTIFICATE_NAME}}/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/{{CERTIFICATE_NAME}}/privkey.pem
    SSLProtocol -all +TLSv1.2 +TLSv1.3

    ProxyRequests Off
    ProxyPreserveHost On
    ProxyTimeout 300
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Port "443"

    # Handles HTTP requests, SSE responses and WebSocket upgrades.
    ProxyPass / http://127.0.0.1:3000/ upgrade=websocket timeout=300
    ProxyPassReverse / http://127.0.0.1:3000/

    # Avoid compression-induced buffering of streamed API responses.
    SetEnvIf Request_URI "^/api/" no-gzip=1

    ErrorLog ${APACHE_LOG_DIR}/memory-ai-error.log
    CustomLog ${APACHE_LOG_DIR}/memory-ai-access.log combined
</VirtualHost>

