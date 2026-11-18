// Inbox Guard data layer: attention model, normalize(), API client, demo backend. Loaded by index.html.
"use strict";
const store = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch { return null; } };
// ---------- attention model (T3 Code's resolveThreadStatusPill, for email) ----------
const KINDS = {
  approval: { label: "Needs Approval", rank: 0, needsYou: true },
  review:   { label: "Review",         rank: 1, needsYou: true },
  blocked:  { label: "Blocked",        rank: 2, needsYou: false },
  scanning: { label: "Scanning",       rank: 3, needsYou: false },
  cleared:  { label: "Cleared",        rank: 4, needsYou: false },
  done:     { label: "Done",           rank: 9, needsYou: false },
};
const seen = new Set(JSON.parse(store("ig.seen") || "[]"));
const markSeen = (id) => { if (!seen.has(id)) { seen.add(id); store("ig.seen", JSON.stringify([...seen].slice(-2000))); } };

function kindOf(d) {
  const s = d.status;
  if (s === "approved" || s === "rejected") return "done";
  if (s === "pending" || s === "processing" || s === "scanning") return "scanning";
  // Suspected injection (quarantine/strip/block) -> Review (pink). A legit email where the agent wants to act -> Approval (amber).
  if (s === "needs_approval") return ["quarantine", "strip", "block"].includes(d.verdict) || !d.action ? "review" : "approval";
  if (d.verdict === "block" || d.verdict === "strip" || s === "blocked") return seen.has(d.id) ? "done" : "blocked";
  return seen.has(d.id) ? "done" : "cleared"; // allowed: shows green until you look at it
}

// ---------- normalize whatever the backend sends ----------
function pick(o, ...keys) { for (const k of keys) { if (o && o[k] != null && o[k] !== "") return o[k]; } return undefined; }
function normalize(raw) {
  const e = raw.email || {};
  let a = pick(raw, "proposed_action", "agent_action", "requested_action", "tool_call");
  if (typeof a === "string") a = { summary: a };
  if (a && typeof a === "object" && !a.summary) a.summary = [a.type || a.name || "action", a.to && `to ${a.to}`].filter(Boolean).join(" ");
  const verdict = String(pick(raw, "verdict", "decision", "action", "label") ?? "").toLowerCase();
  const status = String(pick(raw, "status", "state") ?? (verdict === "allow" ? "allowed" : verdict ? "needs_approval" : "pending")).toLowerCase();
  const created = pick(raw, "created_at", "createdAt", "timestamp", "received_at") ?? new Date().toISOString();
  return {
    id: String(raw.id),
    status,
    verdict: ["allow", "quarantine", "strip", "block"].includes(verdict) ? verdict : verdict || null,
    reason: pick(raw, "reason", "explanation", "rationale") ?? "",
    category: pick(raw, "category", "label_category", "folder") ?? pick(e, "category") ?? "Uncategorized",
    subject: pick(raw, "subject") ?? pick(e, "subject") ?? "(no subject)",
    body: pick(raw, "body", "stripped_body") ?? pick(e, "body") ?? "",
    sender: pick(raw, "sender", "from") ?? pick(e, "sender", "from") ?? "unknown sender",
    action: a && typeof a === "object" ? a : null,
    score: pick(raw, "score", "risk", "confidence"),
    source: pick(raw, "source") ?? pick(e, "source"),
    session: String(pick(raw, "session_id", "thread_id", "conversation_id", "session") ?? pick(e, "thread_id") ?? (pick(raw, "sender", "from") ?? pick(e, "sender", "from") ?? "unknown")),
    created,
    t: Date.parse(created) || Date.now(),
    raw,
  };
}

// ---------- API client, with a demo backend when the real one is unreachable ----------
const DEFAULT_API = "http://localhost:8000";
const qs = new URLSearchParams(location.search).get("api");
let API = (qs || store("ig.api") || DEFAULT_API).replace(/\/$/, "");
let mode = "connecting"; // "live" | "demo"
let hasListAll = true;

async function http(method, path, body) {
  const r = await fetch(API + path, { method, headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) throw Object.assign(new Error(`${method} ${path} -> ${r.status}`), { status: r.status });
  return r.status === 204 ? null : r.json();
}
const asList = (x) => Array.isArray(x) ? x : (x && (x.decisions || x.items || x.data)) || [];

const demo = (() => {
  const db = new Map(); let n = 0;
  const CATS = [
    ["Newsletters", /digest|newsletter|unsubscribe|this week/i],
    ["Finance", /invoice|payment|wire|bank|\$\d|receipt|order #|transfer/i],
    ["Scheduling", /meeting|1:1|calendar|thursday|offsite|agenda|pto|saturday/i],
    ["Security", /password|reset|verify|login|account/i],
    ["Personal", /dinner|lunch|weekend|family/i],
  ];
  const INJ = /api_call|send (an )?e-?mail|contact@contact|ignore (all|previous|prior)|system|assistant|instruction|<\|?|\bexfil|summar/i;
  function classify(e) {
    const text = `${e.subject}\n${e.body}`;
    const category = (CATS.find(([, re]) => re.test(text)) || ["Work"])[0];
    const to = (text.match(/[\w.+-]+\s*@\s*[\w-]+\s*\.\s*\w+/) || [])[0]?.replace(/\s+/g, "");
    if (INJ.test(text)) {
      if (to && /send|forward|email/i.test(text))
        return { category, status: "needs_approval", verdict: "quarantine",
          proposed_action: { type: "send_email", to, summary: `send_email to ${to}` },
          reason: "The email tells the agent to send a message to an address you have never written to. The instruction came from email content, not from you." };
      return { category, status: "needs_approval", verdict: "quarantine", reason: "The email reads like instructions to an AI assistant (talks to the assistant, mentions tools or system prompts). Held for review before the agent reads it." };
    }
    if (/wire|transfer|urgent.*pay/i.test(text))
      return { category, status: "needs_approval", verdict: "allow", proposed_action: { type: "pay", summary: "Draft a $9,800 wire to a new vendor account" }, reason: "Money movement requested by email, from a lookalike domain. Agent will not pay without you." };
    if (/send me|could you send|approve/i.test(text) && e.sender?.endsWith("acme.example"))
      return { category, status: "needs_approval", verdict: "allow", proposed_action: { type: "reply", to: e.sender, summary: `Reply to ${e.sender} with the requested item` }, reason: "Known colleague asked for something. Agent drafted a reply and needs your OK to send it." };
    return { category, status: "allowed", verdict: "allow", reason: "No instructions aimed at the assistant. Passed to the agent." };
  }
  return {
    async post(e) {
      const id = e.id || `demo-${Date.now().toString(36)}-${n++}`;
      const d = { id, subject: e.subject, body: e.body, sender: e.sender, source: e.source, created_at: new Date().toISOString(), status: "pending" };
      db.set(id, d);
      setTimeout(() => Object.assign(d, classify(e)), 900 + Math.random() * 900); // "scanning" for a moment
      return { ...d };
    },
    async list(status) { return [...db.values()].filter((d) => !status || d.status === status).sort((a, b) => b.created_at.localeCompare(a.created_at)).map((d) => ({ ...d })); },
    async resolve(id, how) { const d = db.get(id); if (d) d.status = how === "approve" ? "approved" : "rejected"; return { ...d }; },
    seed() { const s = window.SAMPLE_EMAILS || []; s.slice(0, 22).forEach((e, i) => { const id = `seed-${i}`; db.set(id, { id, ...e, ...classify(e), created_at: new Date(Date.now() - (i + 1) * 4.1 * 60000).toISOString() }); }); },
  };
})();

const api = {
  async postEmail(e) { return mode === "demo" ? demo.post(e) : http("POST", "/emails", { subject: e.subject, body: e.body, sender: e.sender }); },
  async needsApproval() { return mode === "demo" ? demo.list("needs_approval") : asList(await http("GET", "/decisions?status=needs_approval")); },
  async all() {
    if (mode === "demo") return demo.list();
    if (!hasListAll) return null;
    try { return asList(await http("GET", "/decisions")); } catch (e) { if (e.status === 404 || e.status === 405 || e.status === 422) { hasListAll = false; return null; } throw e; }
  },
  async resolve(id, how) { return mode === "demo" ? demo.resolve(id, how) : http("POST", `/decisions/${encodeURIComponent(id)}/${how}`); },
};

