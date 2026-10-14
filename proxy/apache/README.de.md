# Apache-Reverse-Proxy: konfigurierbare Domain

[English](README.md) | **Deutsch**

Apache auf dem Docker-Host übernimmt HTTPS und leitet an `127.0.0.1:3000` weiter.
Apache ab 2.4.47 mit TLS-1.3-Unterstützung verwenden. Bestehende
Cloud-VirtualHosts aktiviert lassen; es wird ein eigener benannter VirtualHost
angelegt.

## Domain einmal konfigurieren

Im Repository-Verzeichnis:

```bash
git pull
nano .env
```

Genau einen `COMPOSE_FILE`-Eintrag setzen und eine bisherige Caddy-Einstellung
ersetzen:

```dotenv
PUBLIC_DOMAIN=ai.example.org
BIND_ADDRESS=127.0.0.1
COMPOSE_FILE=compose.yaml:compose.apache.yaml
```

Die ergänzende Compose-Konfiguration liest `PUBLIC_DOMAIN` für die öffentliche
HTTPS-Adresse von Open WebUI. Einen wörtlichen DNS-Hostnamen ohne Schema, Port,
Pfad oder Wildcard verwenden. Variablenersetzung wie `${OTHER_DOMAIN}` wird vom
Generator nicht unterstützt.

Beide Apache-Konfigurationen erzeugen; benötigt wird Python 3 ohne weitere Pakete:

```bash
python3 scripts/generate_apache.py
```

Ausgaben:

- `generated/apache/memory-ai-http.conf`: HTTP-Konfiguration zur ersten Zertifikatsausstellung.
- `generated/apache/memory-ai.conf`: HTTPS-Proxy, HTTP-Umleitung und ACME-Erneuerung.

Der Generator prüft die Eingaben und erhält Apaches Variable `${APACHE_LOG_DIR}`.
Bei erneutem Aufruf überschreibt er seine erzeugten Dateien. Er installiert keine
Apache-Dateien, stellt keine Zertifikate aus und lädt keine Dienste neu.
Erzeugte Dateien sind von Git ausgeschlossen. Für die Bereitstellung diese
Dateien verwenden; im Repository ist keine domainspezifische Konfiguration
hinterlegt.

Für ein vorhandenes Let's-Encrypt-Zertifikat, das die gewählte Domain abdeckt,
kann dessen Verzeichnisname angegeben werden, beispielsweise:

```dotenv
APACHE_CERTIFICATE_NAME=example.org
```

Damit entstehen Zertifikatspfade unter `/etc/letsencrypt/live/example.org/`.
Leer lassen, um die Domain als Zertifikatsnamen zu verwenden. Der Generator
prüft das Zertifikat nicht; es muss `PUBLIC_DOMAIN` tatsächlich abdecken.
Zertifikate an anderen Speicherorten benötigen vor der Installation angepasste
Zertifikatspfade in der erzeugten Konfiguration.

## Anwendung starten

Falls der mitgelieferte Caddy bereits gestartet wurde, zuerst anhalten:

```bash
docker compose -f compose.yaml -f compose.proxy.yaml stop proxy
```

Den Befehl überspringen, wenn Caddy nicht existiert. Danach:

```bash
docker compose config --quiet
docker compose up -d --build
curl --fail http://127.0.0.1:3000/health
```

Vorausgesetzt wird, dass Apache auf **demselben Host** wie Docker läuft. Bei
Apache in einem Container oder auf einem anderen Rechner bezeichnet
`127.0.0.1` nicht den Docker-Host; die Netzwerkkonfiguration für die Weiterleitung
muss angepasst werden.

## Apache aktivieren und Zertifikat ausstellen

Den A-Eintrag der Domain auf diesen Server zeigen lassen. Ein vorhandener
AAAA-Eintrag muss ihn ebenfalls erreichen. TCP-Ports 80 und 443 müssen Apache
erreichen. Mit `sudo apache2ctl -S` prüfen, dass für die Domain kein doppelter
VirtualHost existiert.

```bash
sudo a2enmod ssl proxy proxy_http headers rewrite setenvif
sudo mkdir -p /var/www/memory-ai-acme/.well-known/acme-challenge
```

Wenn ein passendes Zertifikat bereits vorhanden ist, die folgende erste
Zertifikatsausstellung überspringen und bei **HTTPS aktivieren** fortfahren.
Andernfalls:

```bash
sudo apt install certbot
sudo install -m 644 generated/apache/memory-ai-http.conf /etc/apache2/sites-available/memory-ai-http.conf
sudo a2ensite memory-ai-http
sudo apache2ctl configtest
sudo systemctl reload apache2
```

Nur nach `Syntax OK` neu laden. Das Zertifikat ausstellen, ohne Apache
anzuhalten; `ai.example.org` gegebenenfalls durch die konfigurierte Domain ersetzen:

```bash
sudo certbot certonly --webroot -w /var/www/memory-ai-acme -d ai.example.org --cert-name ai.example.org
```

Certbot kann nach einer Kontaktadresse und der Zustimmung zu den Bedingungen
der Zertifizierungsstelle fragen. Die erzeugte TLS-Datei erst aktivieren, wenn
die darin angegebenen Zertifikatsdateien existieren.

## HTTPS aktivieren

```bash
sudo install -m 644 generated/apache/memory-ai.conf /etc/apache2/sites-available/memory-ai.conf
```

Falls die reine HTTP-Konfiguration für die Zertifikatsausstellung aktiviert
wurde, diese deaktivieren:

```bash
sudo a2dissite memory-ai-http
```

Danach:

```bash
sudo a2ensite memory-ai
sudo apache2ctl configtest
sudo systemctl reload apache2
curl --fail --show-error https://ai.example.org/health
```

Nur nach `Syntax OK` neu laden. Die konfigurierte HTTPS-Domain öffnen, anmelden
und eine Chatnachricht mit Streaming senden. Nur Apache benötigt das Zertifikat;
die Docker-Dienste bleiben dahinter. Bestehende Cloud-VirtualHosts behalten ihre
eigene Konfiguration.

## Erneuerung

Für das oben ausgestellte Webroot-Zertifikat die vorhandene geplante
Certbot-Erneuerung verwenden. Falls Apache danach noch nicht automatisch neu
geladen wird, einen Deploy-Hook ergänzen:

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
sudo certbot renew --cert-name ai.example.org --dry-run
```

Bei anders installiertem Certbot den vorhandenen Erneuerungsmechanismus
beibehalten. Auch bei einem wiederverwendeten Zertifikat dessen bestehenden
Erneuerungsprozess verwenden. Die Domain im Prüfaufruf anpassen, wenn eine
andere konfiguriert wurde.

## Domain später ändern

`PUBLIC_DOMAIN` in `.env` ändern, Dateien erneut erzeugen, ein Zertifikat für
den neuen Hostnamen beschaffen oder ein passendes vorhandenes konfigurieren,
die erzeugte HTTPS-Datei erneut installieren, Apache prüfen und neu laden.
Anschließend `docker compose up -d` ausführen.
DNS und Zertifikatsausstellung werden vom Generator nicht automatisiert.
Durch die Neuinstallation des erzeugten VirtualHosts wird dessen bisheriger
Hostname ersetzt; alte Zertifikatserneuerungseinträge werden nicht automatisch
entfernt.

## Tests

```bash
python3 -m unittest discover -s tests -p test_apache_generator.py -v
```

Diese Tests ohne zusätzliche Abhängigkeiten prüfen Vorlagen, Zertifikatspfade,
Hostname- und Pfadvalidierung, Werte mit Anführungszeichen, doppelte Einstellungen,
erneute Erzeugung sowie Ablehnung ungültiger Eingaben ohne Überschreiben
bestehender Dateien. Sie laufen auch in der Docker-Testsuite.
Apache-`configtest` sowie HTTPS- und Browserprüfungen müssen weiterhin auf dem
Server ausgeführt werden.

## Dokumentation pflegen

Diese Anleitung und [ihre englische Version](README.md) gemeinsam pflegen.
Änderungen an Installation, Konfiguration und Befehlen im selben Commit in
beiden Sprachen vornehmen. Code und Bezeichner bleiben Englisch. Nur neutrale
Beispieldomains und Platzhalter verwenden; echte personenbezogene Angaben
gehören ausschließlich in die lokale Konfiguration.

Referenzen:

- <https://httpd.apache.org/docs/2.4/mod/mod_proxy.html>
- <https://eff-certbot.readthedocs.io/en/stable/using.html>
