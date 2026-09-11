# Merge with your existing Kilo config

Bạn đã có provider/model config thì **không thay toàn bộ `kilo.jsonc`**.

Chỉ thêm:

```jsonc
"instructions": [
  "AGENTS.md",
  ".kilo/rules/*.md"
]
```

Nếu muốn giữ safety defaults, merge thêm:

```jsonc
"permission": {
  "read": {
    "*": "allow",
    "*.env": "ask",
    "*.env.*": "ask",
    "*.env.example": "allow"
  },
  "glob": "allow",
  "grep": "allow",
  "external_directory": "ask",
  "doom_loop": "ask",
  "agent_manager": "deny"
}
```

Lưu ý:
- `agent_manager: deny` không chặn `task` subagents.
- `novel-engineer` chỉ được `task` tới 3 subagent đã allowlist.
- 3 subagent đều có `task: deny`, nên không tạo cây agent vô hạn.

Không cần pin model trong file agent.
Kilo sẽ dùng model/config bạn đang chọn; như vậy không phụ thuộc tên model/provider 9router.
