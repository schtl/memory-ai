# Bootstrap virtual host for HTTP-01 certificate issuance.
<VirtualHost *:80>
    ServerName {{DOMAIN}}
    DocumentRoot /var/www/memory-ai-acme

    <Directory /var/www/memory-ai-acme>
        Options None
        AllowOverride None
        Require all granted
    </Directory>

    ErrorLog ${APACHE_LOG_DIR}/memory-ai-error.log
    CustomLog ${APACHE_LOG_DIR}/memory-ai-access.log combined
</VirtualHost>

