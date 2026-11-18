# Mail Guard: triage service (Track 1)

One Claude call per email returns category, injection flag, proposed action, `can_handle`, confidence.
A deterministic gate (`gate()` in `app.py`) then sets `status`:
`auto_handled` only if the agent can act alone, no injection suspected, action is low-risk, confidence >= 0.8.
Everything else is `needs_approval` and waits for a human on the dashboard. Classifier errors fail closed.

## Run
```
pip install -r requirements.txt
export OPENROUTER_TOKEN=...   # free models via openrouter.ai
uvicorn app:app --port 8000
python feed.py 10      # sample emails from llmail-inject + benign
```

## API for the dashboard (CORS open)
- `POST /emails` `{subject, body, sender?, id?}` -> Decision
- `GET /decisions?status=needs_approval` -> list, newest first
- `POST /decisions/{id}/approve` or `/reject`

Decision statuses: `auto_handled | needs_approval | approved | rejected`. Persisted to `decisions.jsonl`.

## Gmail hookup
Chrome extension content script (or Apps Script on a label trigger) just POSTs `{id, subject, body, sender}` to `/emails`.
