# Safe JSON shelling for contacts.py / outbound.py

Use this pattern when a note or field may contain apostrophes, quotes, parentheses, or other shell-sensitive text:

```python
from hermes_tools import terminal, shell_quote
import json
payload = {
    "name": "Jane Roe",
    "company": "Acme",
    "notes": "...",
}
json_arg = shell_quote(json.dumps(payload))
cmd = f"uv run /home/drc/butler/modules/tools/ppl-index/scripts/contacts.py add --json {json_arg}"
terminal(cmd, timeout=300, workdir='/home/drc/.hermes/profiles/butler')
```

Why this matters:
- Preserves exact punctuation in real notes.
- Avoids shell parse errors from inline quoted JSON.
- One repeatable pattern for `add` / `update` on either tab (swap in `outbound.py` for outreach rows).
