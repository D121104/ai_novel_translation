# Agent Rules

1. Không lấn phase.
2. Không tự thay đổi core architecture nếu chưa có ADR.
3. Không đưa secret vào repository.
4. Không auto merge entity confidence thấp.
5. Không cho model ghi canonical DB trực tiếp.
6. Mọi knowledge phải có provenance/evidence khi có thể.
7. Mọi retrieval phải respect temporal constraints.
8. Mọi job dài phải idempotent và resumable.
9. Chỉ optimize sau khi có benchmark.
10. Mỗi phase phải có test và Definition of Done.
