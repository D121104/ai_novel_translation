# Worker, Retry & Resume Specification

## Queues

- ingestion
- extraction
- embedding
- translation
- qa
- summary
- maintenance

## Early deployment

Development có thể chỉ cần:
- worker-general
- worker-llm

Sau đó mới split.

## Pipeline

```text
ingest
 ↓
extract
 ↓
resolve
 ↓
graph update
 ↓
embed
 ↓
summary
 ↓
translate
 ↓
qa
```

## Idempotency

Idempotency key:
- job_type
- resource_id
- pipeline_version

Retry không được tạo duplicate:
- entity
- fact
- vector
- translation

## Checkpoint

Per novel:
- ingested_until
- extracted_until
- embedded_until
- translated_until
- qa_until
- summarized_until

## Retry classes

Transient:
- timeout
- rate limit
- provider unavailable
- temporary network error

Schema/semantic:
- invalid JSON
- missing fields
- invalid enum

Permanent:
- corrupt input
- unsupported format

## Crash test

Kill worker giữa chapter.
Restart.
System phải resume từ unfinished unit.
