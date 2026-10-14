# Memory AI

A self-hosted chat application with local long-term memory and an external LLM.
No local generative language model is required.

## Architecture

Open WebUI → local memory gateway → LiteLLM → external LLM API.
The gateway searches Qdrant using multilingual local CPU embeddings.

| Service | Purpose | Persistent storage |
| --- | --- | --- |
| Open WebUI | Chat interface and user management | PostgreSQL and `data/openwebui` |
| Memory gateway | Explicit memory commands and retrieval | Qdrant |
| Qdrant | Memory text, vectors and per-user filtering | `data/qdrant` |
| Local embeddings | Semantic search on CPU | `data/embedding-cache` |
| LiteLLM | External provider gateway and overall usage tracking | PostgreSQL |
| PostgreSQL | Separate application and gateway databases | `data/postgres` |

Personal memories use a dedicated Qdrant collection. Open WebUI document RAG
uses separate collections and its own local embedding model.

## Requirements

- Linux server with Docker Engine and Docker Compose v2.
- Approximately 8 GB RAM is a reasonable starting point; no GPU is required.
- An external OpenAI-compatible LLM API key.
- Internet access for initial container and embedding model downloads.

## Quick start

```bash
git clone git@github.com:schtl/memory-ai.git
cd memory-ai
bash setup.sh
nano .env
docker compose config --quiet
docker compose up -d --build
docker compose logs -f memory
```

Set `ADMIN_EMAIL`, `CLOUD_MODEL`, `CLOUD_API_BASE` and `CLOUD_API_KEY` in `.env`.
The setup script generates `ADMIN_PASSWORD` and all local application secrets.
It preserves an existing `.env` file.

```dotenv
ADMIN_EMAIL=admin@example.org
CLOUD_MODEL=openai/YOUR_MODEL_NAME
CLOUD_API_BASE=https://api.openai.com/v1
CLOUD_API_KEY=YOUR_PROVIDER_API_KEY
```

Replace the model name with one available from your provider. For another
OpenAI-compatible provider, use its API base URL and `openai/MODEL_NAME`.
Native Anthropic or Gemini APIs require provider-specific changes to
`litellm.yaml` as well. Initial embedding downloads may take several minutes.

Only Open WebUI publishes a port, bound to `127.0.0.1:3000`. Connect from your
computer using an SSH tunnel:

```bash
ssh -N -L 3000:127.0.0.1:3000 username@server
```

Open <http://localhost:3000> and sign in using `ADMIN_EMAIL` and `ADMIN_PASSWORD`.
Alternatively, configure your existing HTTPS reverse proxy to forward to
`http://127.0.0.1:3000`, including WebSocket support. Sign-up is disabled;
the administrator can create additional users. Select the `memory-ai` model.

## Memory commands

Send each command as a separate chat message:

```text
/remember I teach Java at a technical secondary school.
/remember I publish my teaching materials using Quarto.
/memories
/forget 00000000-0000-0000-0000-000000000000
```

Replace the example UUID with a real memory ID from `/memories`. To correct a
memory, delete the old entry and save the replacement. Each memory may contain
up to 2,000 characters. Saving is explicit: the gateway does not automatically
extract memories from every conversation.

Start a **new chat** and ask, for example, "How should I publish my Java teaching
materials?" The gateway retrieves up to five matching memories and includes
them in the external model request. The similarity threshold in `compose.yaml`
is a starting value, not a guaranteed relevance filter. Tune it after testing.

Open WebUI's built-in memories are disabled because this project uses its own
memory gateway. Enabling them would introduce a second memory system.

## Data boundaries

Your application's databases, files, embeddings and caches are stored under
`data/` on your server. `/remember`, `/memories` and `/forget` are handled locally.
The gateway also removes those command messages and their responses from
subsequent conversation history before forwarding requests.

**Normal requests, their remaining conversation history, attached document
excerpts and retrieved memories are sent to the external LLM provider.**
Provider-side retention depends on the provider's API contract and settings;
this project cannot guarantee that the provider stores nothing.

To stop automatic memory inclusion, set:

```dotenv
SEND_MEMORIES_TO_CLOUD=false
```

Then recreate the gateway:

```bash
docker compose up -d --force-recreate memory
```

Local memory commands still work, but model answers no longer use saved memory.
This does not remove facts already present in normal chat messages. The gateway
does not automatically redact or anonymize arbitrary text.

`/forget` removes the active Qdrant entry. It does not retroactively delete old
chat messages, backups or prompts already sent to an external provider.

## Access and network configuration

PostgreSQL and Qdrant use an internal Docker network without published ports.
The memory gateway requires an API key and the user ID forwarded by Open WebUI.
Requests without a user ID are rejected. User IDs isolate memory retrieval;
this assumes trusted containers and server administrators.

User name and email headers are not forwarded to the model API. Identifying
information inside ordinary message text may still reach the provider.

After successful initial embedding downloads, remove the `outbound` network
from `memory` and `openwebui`. Both can still reach LiteLLM on `backend`; only
LiteLLM then needs outgoing internet access. New model downloads require
temporarily restoring access.

## Operations and backups

```bash
docker compose ps
docker compose logs --tail=100 memory litellm openwebui
```

For a simple consistent backup, briefly stop the services, archive data and
configuration including `.env`, and restart:

```bash
umask 077
docker compose stop
sudo tar -czf "../memory-ai-backup-$(date +%F-%H%M%S).tar.gz" \
  data compose.yaml litellm.yaml .env postgres memory-service
docker compose start
```

Protect backups: they contain personal data and credentials. A backup on the
same disk does not protect against disk failure. To restore, extract into the
project directory while services are stopped, then run
`docker compose up -d --build`. Never delete `data/` as part of a restart.

This starter uses moving container tags and bounded Python dependency ranges.
For ongoing operation, pin tested release tags or image digests and resolved
Python dependency versions. Perform updates deliberately. An embedding model
change requires a matching collection dimension and reindexing into a new
collection; do not simply swap the model name.

LiteLLM tracks overall usage. Individual student budgets and per-user cost
attribution are not configured in this starter.

## Repository and license

Commit project source and `.env.example`. Never commit `.env`, `data/`, backups
or API keys. `.gitignore` excludes these paths. To initialize a new repository:

```bash
git init -b main
git add .
git commit -m "Add self-hosted memory AI stack"
git remote add origin git@github.com:schtl/memory-ai.git
git push -u origin main
```

The remote repository must already exist and your local SSH access must be
configured. This repository uses the Apache License 2.0; see LICENSE.

## Validation status

YAML structure, source syntax and shell syntax have been checked. Gateway logic
checks with fake infrastructure covered local commands, user separation,
deletion authorization, identity checks, filtering of local management turns
from cloud prompts, and optional memory forwarding.

A full container startup, actual embedding download and real cloud API call
have **not** been tested in the authoring environment because Docker and provider
credentials were unavailable. Test with a disposable account before use.

## References

- <https://docs.openwebui.com/reference/env-configuration/>
- <https://docs.openwebui.com/features/chat-conversations/memory/>
- <https://docs.litellm.ai/docs/proxy/docker_quick_start>
- <https://qdrant.tech/documentation/fastembed/>
