# Memory AI

[English](README.md) | **Deutsch**

Eine Chat-Anwendung auf dem eigenen Server mit lokalem Langzeitgedächtnis und
externem LLM. Ein lokales generatives Sprachmodell ist nicht erforderlich.

## Architektur

Open WebUI → lokaler Gedächtnisdienst → LiteLLM → externe LLM-API.
Der Gedächtnisdienst durchsucht Qdrant mit mehrsprachigen, lokal auf der CPU
berechneten Embeddings.

| Dienst | Aufgabe | Dauerhafte Speicherung |
| --- | --- | --- |
| Open WebUI | Chatoberfläche und Benutzerverwaltung | PostgreSQL und `data/openwebui` |
| Gedächtnisdienst | Explizite Speicherbefehle und Abruf | Qdrant |
| Qdrant | Erinnerungstexte, Vektoren und Benutzerfilter | `data/qdrant` |
| Lokale Embeddings | Semantische Suche auf der CPU | `data/embedding-cache` |
| LiteLLM | Zugang zu externen Anbietern und Gesamtverbrauch | PostgreSQL |
| PostgreSQL | Getrennte Datenbanken für Anwendung und Gateway | `data/postgres` |

Persönliche Erinnerungen verwenden eine eigene Qdrant-Collection. Das Dokument-RAG
von Open WebUI verwendet getrennte Collections und ein eigenes lokales
Embedding-Modell.

## Voraussetzungen

- Linux-Server mit Docker Engine und Docker Compose v2.
- Etwa 8 GB RAM sind ein sinnvoller Ausgangspunkt; eine GPU ist nicht erforderlich.
- API-Schlüssel für eine externe, OpenAI-kompatible LLM-API.
- Internetzugang für den ersten Download der Container und Embedding-Modelle.

## Schnellstart

```bash
git clone git@github.com:YOUR_ACCOUNT/memory-ai.git
cd memory-ai
bash setup.sh
nano .env
docker compose config --quiet
docker compose up -d --build
docker compose logs -f memory
```

In `.env` die Werte `ADMIN_EMAIL`, `CLOUD_MODEL`, `CLOUD_API_BASE` und
`CLOUD_API_KEY` setzen. Das Setup-Skript erzeugt `ADMIN_PASSWORD` und alle lokalen
Anwendungsgeheimnisse. Eine vorhandene `.env` bleibt unverändert.

```dotenv
ADMIN_EMAIL=admin@example.org
CLOUD_MODEL=openai/YOUR_MODEL_NAME
CLOUD_API_BASE=https://api.openai.com/v1
CLOUD_API_KEY=YOUR_PROVIDER_API_KEY
```

Den Modellnamen durch ein beim Anbieter verfügbares Modell ersetzen. Für einen
anderen OpenAI-kompatiblen Anbieter dessen API-Adresse und `openai/MODEL_NAME`
verwenden. Native Anthropic- oder Gemini-APIs benötigen zusätzlich
anbieterspezifische Änderungen in `litellm.yaml`. Der erste Download der
Embedding-Modelle kann einige Minuten dauern.

In der Basiskonfiguration veröffentlicht nur Open WebUI einen Port, gebunden an
`127.0.0.1:3000`. Vom eigenen Rechner über einen SSH-Tunnel verbinden:

```bash
ssh -N -L 3000:127.0.0.1:3000 username@server
```

<http://localhost:3000> öffnen und mit `ADMIN_EMAIL` und `ADMIN_PASSWORD` anmelden.
Alternativ einen vorhandenen HTTPS-Reverse-Proxy einschließlich
WebSocket-Unterstützung an `http://127.0.0.1:3000` weiterleiten lassen.
Neuregistrierungen sind deaktiviert; zusätzliche Benutzer legt der Administrator
an. Das Modell `memory-ai` auswählen.

## HTTPS-Reverse-Proxy mit einer Domain

Der optionale Caddy-Proxy ist der einzige öffentliche Zugang. Er beschafft und
erneuert ein Zertifikat für die konfigurierte Domain, leitet HTTP auf HTTPS um
und reicht alle Anwendungspfade einschließlich Streaming und WebSockets an
Open WebUI weiter. PostgreSQL, Qdrant, Gedächtnisdienst und LiteLLM benötigen
keine öffentlichen Zertifikate. TLS endet bei Caddy; die Verbindung zu
Open WebUI verwendet HTTP innerhalb des Docker-Netzwerks.

Voraussetzungen: Docker Compose **ab v2.24.4**, ein öffentlicher DNS-Name, der
auf diesen Server zeigt, und eingehende TCP-Ports 80 und 443, die Caddy über
Firewall/NAT erreichen. Ein vorhandener AAAA-Eintrag muss ebenfalls zum Server
führen. Die Ports müssen frei sein. Sind sie bereits durch einen anderen Proxy
belegt, die Variante mit vorhandenem Proxy verwenden. Rein interne Domains
benötigen eine andere Zertifikatsstrategie, etwa eine interne CA oder eine
DNS-Challenge; diese Konfiguration verwendet öffentliches ACME.

Diese Einträge zur vorhandenen `.env` hinzufügen; sie nicht durch einen erneuten
Setup-Lauf ersetzen:

```dotenv
PUBLIC_DOMAIN=ai.example.org
ACME_EMAIL=admin@example.org
COMPOSE_FILE=compose.yaml:compose.proxy.yaml
```

Hostname und E-Mail-Adresse ersetzen. Nur einen Hostnamen ohne Schema, Port oder
Pfad verwenden. `COMPOSE_FILE` aktiviert die ergänzende Proxy-Konfiguration für
weitere normale Compose-Befehle. Sie entfernt die bisherige Veröffentlichung von
Port 3000 bei Open WebUI.

```bash
git pull
docker compose version
docker compose config --quiet
docker compose up -d --build
docker compose logs --tail=100 proxy
```

`https://ai.example.org` öffnen. Die Zertifikatsausstellung benötigt funktionierende
DNS-Einträge und erreichbare Ports. Zertifikate und private Schlüssel bleiben
unter `data/caddy/` gespeichert und sind in der bestehenden Datensicherung
enthalten. Dieses Verzeichnis bei einer erneuten Bereitstellung nicht löschen.

Die tatsächlich zusammengeführte Port-Konfiguration ohne Containerstart prüfen:

```bash
python3 tests/check_proxy_config.py
```

Die Prüfung benötigt Docker Compose und eine konfigurierte `.env`. Sie prüft,
dass nur Caddy Ports veröffentlicht und Open WebUI eine öffentliche HTTPS-Adresse
verwendet. Die Caddyfile mit dem offiziellen Image prüfen, ohne Zertifikate
anzufordern:

```bash
docker compose run --rm --no-deps proxy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
curl --fail --show-error https://ai.example.org/health
```

Smoke-Test für den bestehenden Stack einschließlich Proxy-Konfiguration:

```bash
docker compose -f compose.yaml -f compose.proxy.yaml -f compose.smoke.yaml run --build --rm --no-deps smoke
```

Der Smoke-Test prüft weiterhin die internen Dienste. Der curl-Befehl prüft den
öffentlichen HTTPS-Zugang einschließlich Zertifikatsprüfung. Anmelden und eine
Chatnachricht mit Streaming senden, um Browser und WebSockets durchgängig zu
prüfen.

### Vorhandener Apache-, Nginx- oder Caddy-Proxy

Für einen vorhandenen Apache-Server `PUBLIC_DOMAIN=ai.example.org` in `.env`
setzen, `python3 scripts/generate_apache.py` ausführen und
[die Apache-Anleitung](proxy/apache/README.de.md) sowie `compose.apache.yaml`
verwenden. Die Anleitung beschreibt Zertifikatsausstellung,
WebSocket-Weiterleitung und Erneuerung, ohne bestehende Cloud-VirtualHosts zu
ersetzen. Dafür `COMPOSE_FILE=compose.yaml:compose.apache.yaml` setzen.

Für andere vorhandene Proxys kann die Basiskonfiguration ohne `COMPOSE_FILE`
verwendet werden. Läuft der Proxy auf demselben Host, die Domain an
`http://127.0.0.1:3000` weiterleiten. WebSocket-Weiterleitung und Streaming
aktivieren und das vorhandene Zertifikat verwenden. Caddy nicht auf bereits
belegten Ports starten. Bei dieser Variante `WEBUI_URL` für Open WebUI in
`compose.yaml` auf die externe HTTPS-Adresse setzen.

## Gedächtnisbefehle

Jeden Befehl als eigene Chatnachricht senden:

```text
/remember I teach Java at a technical secondary school.
/remember I publish my teaching materials using Quarto.
/memories
/forget 00000000-0000-0000-0000-000000000000
```

Die Beispiel-UUID durch eine echte Erinnerungs-ID aus `/memories` ersetzen. Zum
Korrigieren den alten Eintrag löschen und die neue Erinnerung speichern. Jede
Erinnerung darf bis zu 2.000 Zeichen enthalten. Das Speichern erfolgt explizit;
der Gedächtnisdienst extrahiert nicht automatisch Erinnerungen aus jedem Chat.

Einen **neuen Chat** beginnen und beispielsweise fragen, wie die gespeicherten
Unterrichtsmaterialien veröffentlicht werden sollen. Der Dienst ruft bis zu
fünf passende Erinnerungen ab und ergänzt damit die externe Modellanfrage. Die
Ähnlichkeitsschwelle in `compose.yaml` ist ein Ausgangswert und garantiert keine
Relevanz; nach Praxistests anpassen.

Die eingebauten Erinnerungen von Open WebUI sind deaktiviert, weil dieses
Projekt einen eigenen Gedächtnisdienst verwendet. Durch Aktivieren entstünde ein
zweites Gedächtnissystem.

## Grenzen der lokalen Datenhaltung

Datenbanken, Dateien, Embeddings und Caches der Anwendung liegen auf dem Server
unter `data/`. `/remember`, `/memories` und `/forget` werden lokal verarbeitet.
Der Dienst entfernt diese Befehle und ihre Antworten auch aus späteren
Chatverläufen, bevor er Anfragen weiterleitet.

**Normale Anfragen, ihr verbleibender Chatverlauf, eingebundene Dokumentauszüge
und abgerufene Erinnerungen werden an den externen LLM-Anbieter übermittelt.**
Die Aufbewahrung beim Anbieter hängt von dessen API-Vertrag und Einstellungen
ab. Dieses Projekt kann nicht garantieren, dass der Anbieter nichts speichert.

Zum Abschalten der automatischen Einbindung von Erinnerungen setzen:

```dotenv
SEND_MEMORIES_TO_CLOUD=false
```

Danach den Gedächtnisdienst neu erstellen:

```bash
docker compose up -d --force-recreate memory
```

Lokale Gedächtnisbefehle funktionieren weiterhin, Modellantworten verwenden aber
keine gespeicherten Erinnerungen mehr. Fakten, die bereits in normalen
Chatnachrichten stehen, werden dadurch nicht entfernt. Der Dienst anonymisiert
beliebige Texte nicht automatisch.

`/forget` entfernt den aktiven Qdrant-Eintrag. Alte Chatnachrichten, Backups und
bereits an einen Anbieter gesendete Prompts werden nicht rückwirkend gelöscht.

## Zugriff und Netzwerkkonfiguration

PostgreSQL und Qdrant verwenden ein internes Docker-Netzwerk ohne veröffentlichte
Ports. Der Gedächtnisdienst benötigt einen API-Schlüssel und die von Open WebUI
weitergegebene Benutzer-ID. Anfragen ohne Benutzer-ID werden abgewiesen. Die ID
trennt die Erinnerungsabrufe verschiedener Benutzer; vertrauenswürdige Container
und Serveradministratoren werden vorausgesetzt.

Header mit Benutzername und E-Mail-Adresse werden nicht an die Modell-API
weitergegeben. Identifizierende Angaben im normalen Nachrichtentext können den
Anbieter dennoch erreichen.

Nach den ersten erfolgreichen Modell-Downloads kann das Netzwerk `outbound`
bei `memory` und `openwebui` entfernt werden. Beide erreichen LiteLLM weiterhin
über `backend`; nur LiteLLM benötigt dann ausgehenden Internetzugang. Für neue
Modell-Downloads den Zugang vorübergehend wiederherstellen.

## Betrieb und Datensicherung

```bash
docker compose ps
docker compose logs --tail=100 memory litellm openwebui
```

Für eine einfache konsistente Sicherung die Dienste kurz anhalten, Daten und
Konfiguration einschließlich `.env` archivieren und wieder starten:

```bash
umask 077
docker compose stop
sudo tar -czf "../memory-ai-backup-$(date +%F-%H%M%S).tar.gz" \
  data compose*.yaml litellm.yaml .env postgres memory-service proxy
docker compose start
```

Backups schützen: Sie enthalten persönliche Daten und Zugangsschlüssel. Eine
Sicherung auf derselben Festplatte schützt nicht vor deren Ausfall. Zur
Wiederherstellung bei angehaltenen Diensten in das Projektverzeichnis entpacken
und `docker compose up -d --build` ausführen. `data/` bei einem Neustart niemals
löschen.

Die Vorlage verwendet veränderliche Container-Tags und begrenzte
Versionsbereiche für Python-Abhängigkeiten. Für den Dauerbetrieb getestete
Release-Tags oder Image-Digests und konkrete Python-Versionen festlegen. Updates
bewusst durchführen. Ein Wechsel des Embedding-Modells benötigt eine passende
Collection-Dimension und eine erneute Indexierung in eine neue Collection;
nicht einfach den Modellnamen austauschen.

LiteLLM erfasst den Gesamtverbrauch. Individuelle Schülerbudgets und
benutzerspezifische Kostenzuordnung sind in dieser Vorlage nicht eingerichtet.

## Repository und Lizenz

Quellcode und `.env.example` versionieren. `.env`, `data/`, Backups und
API-Schlüssel niemals committen; `.gitignore` schließt diese Pfade aus. Ein neues
Repository initialisieren:

```bash
git init -b main
git add .
git commit -m "Add self-hosted memory AI stack"
git remote add origin git@github.com:YOUR_ACCOUNT/memory-ai.git
git push -u origin main
```

Das entfernte Repository muss bereits existieren und der lokale SSH-Zugriff
muss eingerichtet sein. Dieses Repository verwendet die Apache License 2.0;
siehe `LICENSE`.

## Fehler beim Start des Embedding-Modells

Wenn der Start meldet, dass `intfloat/multilingual-e5-small` nicht unterstützt
wird, den Gedächtnisdienst aktualisieren und neu bauen:

```bash
git pull
docker compose up -d --build
docker compose logs --tail=100 -f memory
```

Das Gedächtnis verwendet jetzt
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, das in FastEmbed
mit 384 Dimensionen registriert ist. Es verarbeitet reinen Text ohne E5-Präfixe.
Seine Vektoren liegen in der neuen Collection
`personal_memories_multilingual_minilm_v1`; die bisherige Collection bleibt
erhalten und wird nicht mit dem neuen Embedding-Raum vermischt. Bestehende
Einträge aus der alten Collection werden nicht automatisch migriert.

Den vollständigen Stack starten, damit Qdrant und die anderen Abhängigkeiten
laufen. Bei einem gestoppten Stack `memory` nicht mit `--no-deps` starten:
Der Hostname `qdrant` kann dann nicht aufgelöst werden. Falls der Fehler bleibt,
mit `docker compose ps -a` und `docker compose logs --tail=100 qdrant` nach
einem gestoppten oder fehlgeschlagenen Dienst suchen.

Beim Start werden Modellregistrierung und Dimension vor dem Download geprüft.
Die Docker-Tests prüfen zusätzlich das echte Modellverzeichnis der installierten
FastEmbed-Version ohne Modell-Download. Die bisherigen HTTP-Tests verwendeten
ein simuliertes Embedding-Modell und erkannten diesen Fehler deshalb nicht.
Beim ersten erfolgreichen Start wird das Modell weiterhin heruntergeladen;
der Gedächtnisdienst benötigt bis zum Befüllen seines Caches Internetzugang.
Sobald er gesund ist, gegebenenfalls das wartende Open WebUI mit
`docker compose up -d openwebui` starten.

## Tests

Die isolierten Regressionstests für den Gedächtnisdienst in Docker ausführen:

```bash
docker compose -f compose.test.yaml run --build --rm tests
```

Dieser Befehl benötigt keine `.env`, keinen Anbieter-Schlüssel, keine
Produktionsdatenbank und keinen laufenden Anwendungsstack. Die Tests verwenden
die tatsächlichen FastAPI-Endpunkte und den echten Qdrant-Client im
In-Memory-Modus. Embeddings sind deterministische Testvektoren; LiteLLM-Antworten
werden über einen HTTP-Mock simuliert. Zur Laufzeit hat der Testcontainer keinen
Netzwerkzugriff. Abhängigkeiten werden nur beim Image-Build heruntergeladen.

Geprüft werden lokale Speicheroperationen, Pagination, Authentifizierung,
benutzerübergreifende Zugriffssperren, Relevanz und Löschung beim Abruf,
abgeschaltete Gedächtnisweitergabe, Chatverlaufsfilterung, Entfernen von
Identitäts-Headern und Metadaten, Streaming, Fehler des Anbieters und ungültige
Anfragen. Die semantische Qualität des echten Embedding-Modells wird nicht
bewertet; es gibt keine kostenpflichtigen Cloud-Aufrufe.

Den **bereits laufenden** Anwendungsstack gesondert prüfen:

```bash
docker compose up -d --build
docker compose -f compose.yaml -f compose.smoke.yaml run --build --rm --no-deps smoke
```

Der Smoke-Test prüft die Erreichbarkeit von Open WebUI, LiteLLM und Gedächtnisdienst.
Mit echten CPU-Embeddings und Qdrant speichert, listet, trennt und löscht er eine
temporäre Erinnerung. Er verwendet zufällige künstliche Benutzer-IDs und räumt
seine Einträge auf. Er sendet keine normale Chat-Anfrage an das externe LLM.
PostgreSQL wird nicht direkt abgefragt. Die vollständige Anmeldung und
Chatbedienung in Open WebUI sowie die Anbieteranbindung benötigen weiterhin
einen durchgängigen Test mit dem konfigurierten Anbieter.

Beide Befehle liefern bei Fehlern einen Exit-Status ungleich null. Bei einem
fehlgeschlagenen Smoke-Test die Logs mit
`docker compose logs --tail=100 memory` ansehen. Einen gestoppten Stack zuerst
starten; `--no-deps` verhindert, dass der Smoke-Test selbst Produktionsdienste
startet oder neu konfiguriert.

## Dokumentation pflegen

Englisch und Deutsch sind gleichwertige, gemeinsam gepflegte Versionen:
`README.md` und `README.de.md` sowie die entsprechenden Apache-Anleitungen.
Änderungen an Verhalten, Konfiguration, Befehlen, Voraussetzungen und Grenzen
müssen im selben Commit in beiden Sprachen erfolgen. Namen von Dateien,
Variablen, Befehlen und Programmcode bleiben Englisch. Beispiele verwenden nur
neutrale Platzhalter; echte Domains, Kontonamen, Kontaktdaten und Zugangsschlüssel
gehören nicht in die öffentliche Dokumentation.

## Stand der Validierung

YAML-Struktur sowie Python- und Shell-Syntax wurden geprüft. Die eingecheckten
Regressionstests verwenden FastAPI, Qdrant im In-Memory-Modus, deterministische
Embeddings und HTTP-Mocks. In der Erstellungsumgebung war die Installation von
Testabhängigkeiten blockiert; deshalb wurden diese Suite und der Docker-Smoke-Test
dort nicht ausgeführt. Die genannten Befehle auf dem Docker-Host ausführen.

Die neun Apache-Generator-Tests ohne zusätzliche Abhängigkeiten wurden ausgeführt
und bestanden. Sie prüfen Eingaben, Vorlagen, Zertifikatspfade und erneute Erzeugung.

Ein vollständiger Containerstart, echter Embedding-Download und echter
Cloud-API-Aufruf wurden in der Erstellungsumgebung **nicht** getestet, da Docker
und Anbieter-Zugangsschlüssel nicht verfügbar waren. Vor der Nutzung mit einem
Testkonto prüfen.

## Referenzen

- <https://docs.openwebui.com/reference/env-configuration/>
- <https://docs.openwebui.com/features/chat-conversations/memory/>
- <https://docs.litellm.ai/docs/proxy/docker_quick_start>
- <https://qdrant.tech/documentation/fastembed/>
- <https://caddyserver.com/docs/automatic-https>
- <https://caddyserver.com/docs/caddyfile/directives/reverse_proxy>
- <https://docs.docker.com/reference/compose-file/merge/>
