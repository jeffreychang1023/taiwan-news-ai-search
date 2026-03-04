# Qdrant Profile Switching Specification

## Overview

Profile-based switching system for safely alternating between online/offline Qdrant configurations.
A single environment variable (`QDRANT_PROFILE`) controls both **indexing** and **query** systems simultaneously.

---

## Problem

The system has two independent Qdrant configurations that differ in every aspect:

| Aspect | Indexing (Offline) | Query (Online) |
|--------|-------------------|----------------|
| Config source | Environment variables | `config_retrieval.yaml` |
| Collection | `nlweb` | `nlweb_collection` |
| Embedding | bge-m3 (1024D) | OpenAI (1536D) |
| Client | Sync `QdrantClient` | Async `AsyncQdrantClient` |
| Payload | 13 fields (chunk metadata) | 4 fields (url, name, site, schema_json) |

Switching manually requires changing multiple files and env vars, risking dimension mismatches
that silently corrupt the vector database.

---

## Solution: Profile Overlay

### Architecture

```
QDRANT_PROFILE env var
       │
       ▼
config_qdrant_profiles.yaml   ←── Profile definitions
       │
       ▼
core/qdrant_profile.py        ←── Profile manager (load, validate, apply)
       │
       ├──► AppConfig.__init__()     ←── Overrides: embedding provider, endpoint, collection
       ├──► indexing/embedding.py    ←── Routes to correct embedding model
       └──► indexing/qdrant_uploader.py  ←── Routes to correct Qdrant instance
```

### Profile Definition

Each profile bundles:
- **Qdrant connection**: URL, API key, collection name
- **Embedding provider**: model name, dimension
- **Retrieval endpoint**: which `config_retrieval.yaml` endpoint to activate

### Data Flow

```
AppConfig.__init__()
  ├── load_embedding_config()       → preferred_embedding_provider = "openai"
  ├── load_retrieval_config()       → write_endpoint = "qdrant_url", endpoints loaded
  └── _apply_qdrant_profile()       ← Last step (overlay)
        ├── Read QDRANT_PROFILE env var
        ├── Load config_qdrant_profiles.yaml
        ├── Validate collection dimension against Qdrant
        └── Override CONFIG attributes:
              ├── preferred_embedding_provider → profile's provider
              ├── retrieval_endpoints[endpoint].index_name → profile's collection
              └── write_endpoint → profile's endpoint
```

---

## Profiles

### `offline`

| Setting | Value |
|---------|-------|
| Collection | `nlweb` |
| Embedding | `huggingface` / `BAAI/bge-m3` |
| Dimension | 1024 |
| Qdrant | Cloud (from `QDRANT_URL` env var) |

### `online`

| Setting | Value |
|---------|-------|
| Collection | `nlweb_collection` |
| Embedding | `openai` / `text-embedding-3-small` |
| Dimension | 1536 |
| Qdrant | Cloud (from `QDRANT_URL` env var) |

---

## Usage

```bash
# Offline: bge-m3 + nlweb collection
QDRANT_PROFILE=offline python -m indexing.pipeline articles.tsv --upload
QDRANT_PROFILE=offline python -m webserver.aiohttp_server

# Online: OpenAI + nlweb_collection
QDRANT_PROFILE=online python -m indexing.pipeline articles.tsv --upload
QDRANT_PROFILE=online python -m webserver.aiohttp_server

# No profile: backward compatible (indexing uses bge-m3, query uses openai)
python -m webserver.aiohttp_server
```

---

## Safety Mechanisms

### Dimension Validation (Startup)

At boot, the system connects to Qdrant and checks:
1. If the collection exists, verify its vector dimension matches the profile
2. If dimensions mismatch → **ValueError, blocks startup**
3. If collection doesn't exist → log info, proceed (will be created on first upload)
4. If Qdrant is unreachable → log warning, proceed

### Fail-Fast on Invalid Profile

If `QDRANT_PROFILE` is set to an unknown name → **ValueError with available profiles listed**.

### Backward Compatibility

When `QDRANT_PROFILE` is not set:
- `_apply_qdrant_profile()` is a no-op
- `get_active_profile()` returns `None`
- `QdrantConfig.from_env()` uses raw env vars
- `indexing/embedding.py` uses bge-m3
- All behavior is identical to pre-profile system

---

## Files

| File | Role |
|------|------|
| `config/config_qdrant_profiles.yaml` | Profile definitions (YAML) |
| `code/python/core/qdrant_profile.py` | Profile manager: load, validate, apply, cache |
| `code/python/core/config.py` | `_apply_qdrant_profile()` hook in `AppConfig.__init__` |
| `code/python/indexing/embedding.py` | Routes `embed_texts()` / `get_embedding_dimension()` by profile |
| `code/python/indexing/qdrant_uploader.py` | `QdrantConfig.from_env()` checks profile first |

## Key APIs

### `core.qdrant_profile`

| Function | Returns | Description |
|----------|---------|-------------|
| `get_active_profile()` | `QdrantProfile \| None` | Cached active profile |
| `load_qdrant_profile(config_dir)` | `QdrantProfile \| None` | Load from YAML + env var |
| `apply_profile_to_config(profile, config)` | `None` | Mutate AppConfig |
| `get_active_qdrant_config()` | `QdrantConfig \| None` | For indexing pipeline |

### `QdrantProfile` dataclass

```python
@dataclass
class QdrantProfile:
    name: str               # "online" or "offline"
    description: str
    qdrant_url: str          # Resolved from env var
    qdrant_api_key: str | None
    collection: str          # Target collection name
    embedding_provider: str  # "openai" or "huggingface"
    embedding_model: str     # Model identifier
    dimension: int           # Vector dimension (1024 or 1536)
    retrieval_endpoint: str  # config_retrieval.yaml endpoint name
```

---

## Adding a New Profile

1. Add entry to `config/config_qdrant_profiles.yaml`:
   ```yaml
   profiles:
     my_profile:
       description: "Custom profile"
       qdrant:
         url_env: MY_QDRANT_URL
         api_key_env: MY_QDRANT_KEY
         collection: my_collection
       embedding:
         provider: openai
         model: text-embedding-3-large
         dimension: 3072
       retrieval_endpoint: qdrant_url
   ```

2. Set env vars: `MY_QDRANT_URL`, `MY_QDRANT_KEY`

3. Activate: `QDRANT_PROFILE=my_profile`

---

*Created: 2026-02-11*
