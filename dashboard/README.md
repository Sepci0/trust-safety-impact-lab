# Inbox Guard dashboard

A T3 Code-style attention sidebar for the inbox firewall. See [T3_ATTENTION_REPORT.md](T3_ATTENTION_REPORT.md) for the pattern it copies.

```bash
python3 -m http.server 5173 --directory dashboard        # then open http://localhost:5173/?api=http://localhost:8000
python3 dashboard/mock_api.py                            # optional stand-in API on :8000 (same contract)
```

No build step. With no API reachable it falls back to demo data (real LLMail-Inject attack emails), so it always demos.

## Tags (one per email, most urgent wins)

| Tag | Color | When | Buttons |
|---|---|---|---|
| Needs Approval | amber | `status=needs_approval`, verdict `allow`, agent proposes an action | Approve action / Reject |
| Review | pink | `status=needs_approval`, verdict `quarantine`/`strip`/`block` (suspected injection) | Release to agent / Keep quarantined |
| Blocked | red | verdict `block`/`strip`, not yet opened | – |
| Scanning | sky, pulsing | `status=pending` | – |
| Cleared | green | allowed, not yet opened | – |
| Done | gray | `approved` / `rejected`, or opened | – |

## Decision fields it reads

`id` (required), `status`, `verdict`, `reason`, `category`, `subject`/`body`/`sender` (top level or under `email`),
`proposed_action` (`{type, to, summary}` or a string), `created_at`. Aliases are handled in `normalize()` in index.html.
`GET /decisions` without a filter is optional: without it, categories only show items that need approval.

Keys: `J`/`K` move, `A` approve, `R` reject, `Esc` deselect.
