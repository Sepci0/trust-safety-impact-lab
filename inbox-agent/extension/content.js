// Detects an opened Gmail message, sends it to the agent once, and shows the decision next to the subject.
const seen = new Set();

function readOpenEmail() {
  const subjectEl = document.querySelector("h2.hP");
  const bodyEl = document.querySelector("div.a3s.aiL") || document.querySelector("div.a3s");
  if (!subjectEl || !bodyEl) return null;
  const senderEl = document.querySelector("span.gD");
  const msgEl = document.querySelector("[data-legacy-message-id]");
  const subject = subjectEl.innerText.trim();
  const body = bodyEl.innerText.trim();
  return {
    id: msgEl?.getAttribute("data-legacy-message-id") || `${subject}|${body.length}`,
    subject,
    body,
    sender: senderEl?.getAttribute("email") || senderEl?.innerText || null,
  };
}

function badge(subjectEl, text, color) {
  let el = document.getElementById("triage-badge");
  if (!el) {
    el = document.createElement("span");
    el.id = "triage-badge";
    el.style.cssText = "margin-left:12px;padding:3px 10px;border-radius:12px;font:600 12px sans-serif;color:#fff;";
    subjectEl.appendChild(el);
  }
  el.textContent = text;
  el.style.background = color;
}

function check() {
  const email = readOpenEmail();
  if (!email || seen.has(email.id)) return;
  seen.add(email.id);
  const subjectEl = document.querySelector("h2.hP");
  badge(subjectEl, "Agent: checking…", "#888");
  chrome.runtime.sendMessage({ type: "triage", email }, (res) => {
    if (!res?.ok) return badge(subjectEl, "Agent: offline", "#b00020");
    const d = res.decision;
    const auto = d.status === "auto_handled";
    const label = auto ? `Agent handled: ${d.proposed_action}` : "Needs your approval";
    badge(subjectEl, `${label}${d.injection_suspected ? " ⚠ injection" : ""}`, auto ? "#1b8a3a" : "#c77700");
    subjectEl.title = d.reason;
  });
}

// Gmail is a single-page app: watch for DOM changes instead of page loads.
new MutationObserver(() => check()).observe(document.body, { childList: true, subtree: true });
check();
