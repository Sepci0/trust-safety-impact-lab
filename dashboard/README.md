# Inbox Guard dashboard

A T3 Code-style attention dashboard for the inbox firewall, laid out from the team wireframe:

- **Left:** sessions that need you (category label, title, tag on the right), then **Settled**: sessions with nothing waiting on you, each still labeled with its category.
- **Center:** actions needed for the open session (Approve / Reject, plus Approve all / Reject all), then the session's emails stacked like a chat.
- **Right:** the category, its rules (editable), and a category chat.

A session is a thread of emails: `session_id` / `thread_id` / `conversation_id` on the Decision if the backend sends one, otherwise one session per sender. Rules and chat are stored in the browser. Chat calls `POST /categories/{name}/chat {message, rules}` -> `{reply, rules?}` if the API has it; otherwise a labeled demo responder answers and turns "always/never/..." messages into rules.

The page is See [T3_ATTENTION_REPORT.md](T3_ATTENTION_REPORT.md) for the pattern it copies.

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
