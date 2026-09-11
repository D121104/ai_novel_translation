# Temporal Knowledge Specification

## Problem

Nếu index toàn bộ novel rồi retrieve không giới hạn, chapter đầu có thể nhận knowledge
từ chapter tương lai và gây spoiler hoặc sai logic.

## Canonical ordering

Mỗi translation unit có:

```text
source_order
```

Khuyến nghị:
- bigint tăng đơn điệu
- hoặc tuple `(chapter_index, unit_index)`

Ví dụ:
- Chapter 1 Unit 1 → 1000001
- Chapter 532 Unit 8 → 532000008

## Fact time fields

- `observed_at_order`
- `valid_from_order`
- `valid_to_order`

## Retrieval rule

Mọi query cho vị trí hiện tại phải thỏa:

```text
observed_at_order <= current_order
```

và nếu query relation đang active:

```text
valid_from_order <= current_order
AND (valid_to_order IS NULL OR valid_to_order >= current_order)
```

## Two knowledge modes

### Strict Story Knowledge
Chỉ dùng knowledge đã xuất hiện tại thời điểm hiện tại.

### Global Consistency
Cho phép metadata không gây spoiler:
- spelling chuẩn
- target-language canonical name
- gender
- locked glossary

Không cho:
- future death
- future betrayal
- unrevealed identity
- future relationship

## Character-specific knowledge

Có thể biểu diễn:
```text
(Character)-[:KNOWS_FACT]->(Fact)
```

Cho phép phân biệt:
- sự thật của thế giới
- điều nhân vật A biết
- điều nhân vật B chưa biết
