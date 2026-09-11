# Phase 0 Recommended Execution Order

1. Initialize repository and uv.
2. Copy/adapt `pyproject.toml`.
3. Create package/folder skeleton.
4. Implement settings/config.
5. Implement structured logging.
6. Implement infrastructure health adapters one by one:
   - PostgreSQL
   - Redis
   - Qdrant
   - Neo4j
   - MinIO
7. Implement `/health`.
8. Implement readiness aggregator.
9. Implement `/ready`.
10. Add unit tests.
11. Add integration tests.
12. Add pre-commit.
13. Bring up Docker Compose.
14. Run quality gates.
15. Update README.
16. Stop. Do not start Phase 1.
