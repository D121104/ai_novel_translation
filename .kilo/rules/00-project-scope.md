# Project Scope Rule

This is a **personal novel translation application**, not a SaaS product.

## Default decisions

Prefer:
- local-first development;
- one backend repository;
- explicit Python code;
- simple deployment;
- the smallest solution that preserves correctness.

Do not add without an explicit requirement:
- authentication;
- RBAC;
- multi-tenancy;
- Kubernetes;
- Kafka;
- service mesh;
- microservices;
- distributed tracing;
- enterprise secrets infrastructure;
- complex event sourcing;
- LangChain/LangGraph;
- autonomous agent frameworks;
- unnecessary cloud services.

## Phase discipline

Only implement the requested/current phase.

A future-phase change is allowed only when it is a tiny prerequisite needed to complete
the current phase safely. State that exception explicitly.

Do not silently redesign the whole project.
