# Coding Rule

## Python

Target:
- Python 3.12
- uv
- FastAPI
- Pydantic v2
- SQLAlchemy 2
- pytest
- Ruff
- mypy

## Style

- Use type hints on public functions and important internal boundaries.
- Prefer small functions/classes with one responsibility.
- Prefer explicit domain behavior over clever abstractions.
- Avoid premature generic frameworks.
- Keep I/O at infrastructure boundaries.
- Keep business rules testable without requiring all databases.
- Use async only where it provides real I/O benefit.
- Do not mix sync/async accidentally.

## Configuration

- No credentials in source code.
- Use settings/environment configuration.
- Never commit `.env`.
- `.env.example` contains placeholders only.
- Never log passwords, tokens, API keys, connection credentials or raw secrets.

## Dependencies

Before adding a dependency:
1. verify the standard library/current dependency cannot do it simply;
2. state why it is needed;
3. avoid duplicate libraries for the same job.

Do not introduce LangChain/LangGraph for convenience wrappers.

## Changes

- Avoid unrelated refactors while implementing a scoped task.
- Preserve public behavior unless the task explicitly changes it.
- Prefer migrations over destructive schema recreation once persistent data exists.
- Avoid deleting user data or Docker volumes automatically.
