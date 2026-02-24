# NLWeb Development Setup

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows / Mac / Linux)
- Git

## Quick Start (5 minutes)

```bash
# 1. Clone the repo
git clone <repo-url>
cd nlweb

# 2. Set up environment variables
cp .env.example .env
# Edit .env and fill in your API keys (at minimum: OPENAI_API_KEY, QDRANT_URL, QDRANT_API_KEY)

# 3. Build and run (first time takes ~3 minutes)
docker compose up --build

# Server will be available at http://localhost:8000
```

## Development Mode (live code editing)

```bash
# Start with live code mounting - your edits take effect on restart
docker compose --profile dev up nlweb-dev --build
```

In dev mode, `code/` is mounted into the container. Edit files locally with your IDE, restart the container to see changes.

## Common Commands

```bash
# Rebuild after changing requirements.txt
docker compose build --no-cache

# View logs
docker compose logs -f

# Open a shell inside the container
docker compose exec nlweb bash
# Or for dev mode:
docker compose --profile dev exec nlweb-dev bash

# Stop everything
docker compose down
```

## Environment Variables

See `.env.example` for all available variables with descriptions.

**Required for basic operation:**
- `OPENAI_API_KEY` - LLM provider
- `QDRANT_URL` + `QDRANT_API_KEY` - Vector database

## Python Version

This project uses **Python 3.11** (not 3.13). The Docker image handles this automatically.

## Without Docker (not recommended)

If you must run without Docker:

```bash
# Requires Python 3.11
python -m venv venv
source venv/bin/activate  # Mac/Linux
# or: venv\Scripts\activate  # Windows

pip install -r requirements.txt
cd code/python
python app-file.py
```

Note: Some dependencies (chroma-hnswlib, psycopg) require C/C++ compilers. Docker avoids this issue entirely.
