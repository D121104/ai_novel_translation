# Phase 0 Folder Structure

```text
novel-translator/
├── apps/
│   ├── __init__.py
│   └── api/
│       ├── __init__.py
│       └── main.py
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── logging.py
│   └── infrastructure/
│       ├── __init__.py
│       ├── postgres/
│       │   ├── __init__.py
│       │   └── health.py
│       ├── neo4j/
│       │   ├── __init__.py
│       │   └── health.py
│       ├── qdrant/
│       │   ├── __init__.py
│       │   └── health.py
│       ├── redis/
│       │   ├── __init__.py
│       │   └── health.py
│       └── minio/
│           ├── __init__.py
│           └── health.py
├── tests/
│   ├── unit/
│   └── integration/
├── docs/
├── infrastructure/
│   └── docker/
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Phase 0 boundary

Chưa tạo:
- `domain/novel`
- `knowledge/`
- `retrieval/`
- `translation/`
- `frontend/`

Các folder đó được tạo ở phase tương ứng.
