// Content scripts on Gmail can be blocked by CSP when calling localhost, so the service worker does the fetch.
const API = "http://localhost:8000";

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type !== "triage") return;
  fetch(`${API}/emails`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(msg.email),
  })
    .then((r) => r.json())
    .then((d) => sendResponse({ ok: true, decision: d }))
    .catch((e) => sendResponse({ ok: false, error: String(e) }));
  return true; // async response
});
