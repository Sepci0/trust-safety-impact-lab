#!/usr/bin/env python3
"""Stand-in for the real firewall API, same contract, so the dashboard can be built and demoed.

  POST /emails {subject, body, sender?, id?}   -> Decision
  GET  /decisions[?status=needs_approval]      -> Decision[] newest first
  POST /decisions/{id}/approve | /reject       -> Decision

Run: python dashboard/mock_api.py  (port 8000). Keyword heuristic only; swap in the real backend.
"""
import json, re, uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB = {}
INJ = re.compile(r"api_call|send (an )?e-?mail|contact@contact|ignore (all|previous|prior)|system|assistant|instruction", re.I)
ADDR = re.compile(r"[\w.+-]+\s*@\s*[\w-]+\s*\.\s*\w+")
CATS = [("Finance", r"invoice|payment|wire|bank|\$\d|receipt"), ("Scheduling", r"meeting|1:1|calendar|offsite|pto"),
        ("Security", r"password|reset|verify|login"), ("Newsletters", r"digest|newsletter|unsubscribe")]


def decide(e):
    text = f"{e.get('subject','')}\n{e.get('body','')}"
    cat = next((c for c, p in CATS if re.search(p, text, re.I)), "Work")
    d = {"id": e.get("id") or uuid.uuid4().hex[:12], "subject": e.get("subject", ""), "body": e.get("body", ""),
         "sender": e.get("sender") or "unknown@external", "category": cat,
         "created_at": datetime.now(timezone.utc).isoformat()}
    if INJ.search(text):
        to = ADDR.search(text)
        d.update(status="needs_approval", verdict="quarantine",
                 reason="Text addressed to the assistant / tool names found in an inbound email.")
        if to:
            d["proposed_action"] = {"type": "send_email", "to": re.sub(r"\s+", "", to.group())}
    else:
        d.update(status="allowed", verdict="allow", reason="No instructions aimed at the assistant.")
    return d


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj=None):
        body = b"" if obj is None else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204)

    def do_GET(self):
        path, _, q = self.path.partition("?")
        if path != "/decisions":
            return self._send(404, {"error": "not found"})
        status = dict(p.split("=", 1) for p in q.split("&") if "=" in p).get("status")
        rows = [d for d in DB.values() if not status or d["status"] == status]
        self._send(200, sorted(rows, key=lambda d: d["created_at"], reverse=True))

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        data = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/emails":
            d = decide(data)
            DB[d["id"]] = d
            return self._send(200, d)
        m = re.fullmatch(r"/decisions/([^/]+)/(approve|reject)", self.path)
        if m and m.group(1) in DB:
            DB[m.group(1)]["status"] = "approved" if m.group(2) == "approve" else "rejected"
            return self._send(200, DB[m.group(1)])
        self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        print(fmt % args)


if __name__ == "__main__":
    print("mock API on http://localhost:8000")
    ThreadingHTTPServer(("127.0.0.1", 8000), H).serve_forever()
