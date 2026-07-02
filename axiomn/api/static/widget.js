/* AXIOMN Everywhere — the embeddable intent widget.
 *
 * One script tag gives ANY website a voice-capable intent assistant
 * backed by an AXIOMN instance — the way Analytics gave every site
 * measurement and Intercom gave every site chat:
 *
 *   <script src="https://axiomn.fly.dev/ui/widget.js" defer
 *           data-axiomn-key="YOUR_KEY"></script>
 *
 * Optional attributes:
 *   data-axiomn-url  — API base (defaults to this script's own origin)
 *   data-axiomn-key  — X-API-Key sent with every request
 *
 * Self-contained: no dependencies, Shadow DOM so host-page CSS can't
 * bleed in, speech in/out via the browser's own APIs, and the same
 * routing transparency as the /ui/ demo (route, model, why).
 */
(function () {
  "use strict";
  const script = document.currentScript;
  const base = (script && script.dataset.axiomnUrl) || (script ? new URL(script.src).origin : "");
  const apiKey = (script && script.dataset.axiomnKey) || "";

  const host = document.createElement("div");
  const root = host.attachShadow({ mode: "open" });
  root.innerHTML = `
    <style>
      .orb { position: fixed; bottom: 24px; right: 24px; width: 56px; height: 56px;
             border-radius: 50%; border: none; background: #5b8cff; color: #fff;
             font-size: 1.5rem; cursor: pointer; box-shadow: 0 4px 14px rgba(0,0,0,.35);
             z-index: 2147483000; }
      .panel { position: fixed; bottom: 92px; right: 24px; width: 340px; max-width: calc(100vw - 48px);
               background: #0b0d12; color: #e6e9ef; border: 1px solid #2a2f3d; border-radius: 12px;
               padding: 14px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
               font-size: .95rem; display: none; z-index: 2147483000; }
      .row { display: flex; gap: 6px; }
      input { flex: 1; background: #151823; border: 1px solid #2a2f3d; color: #e6e9ef;
              border-radius: 8px; padding: 9px 10px; font-size: .95rem; }
      button.small { background: #151823; border: 1px solid #2a2f3d; color: #e6e9ef;
                     border-radius: 8px; padding: 0 12px; cursor: pointer; font-size: 1rem; }
      button.go { background: #5b8cff; border: none; color: #fff; border-radius: 8px;
                  padding: 0 14px; cursor: pointer; }
      .answer { margin-top: 10px; white-space: pre-wrap; line-height: 1.45; display: none; }
      .why { margin-top: 8px; font-size: .75rem; color: #9aa3b8; border-left: 2px solid #2a2f3d;
             padding-left: 8px; display: none; }
      .brand { margin-top: 10px; font-size: .7rem; color: #6b7280; text-align: right; }
      .brand a { color: #8b92a5; }
    </style>
    <button class="orb" part="orb" title="AXIOMN">⚡</button>
    <div class="panel" part="panel">
      <div class="row">
        <input type="text" placeholder="Demandez n'importe quoi..." />
        <button class="small mic" style="display:none">🎤</button>
        <button class="go">→</button>
      </div>
      <div class="answer"></div>
      <div class="why"></div>
      <div class="brand">powered by <a href="${base}/ui/" target="_blank" rel="noopener">AXIOMN</a></div>
    </div>`;
  document.addEventListener("DOMContentLoaded", () => document.body.appendChild(host));
  if (document.body) document.body.appendChild(host);

  const orb = root.querySelector(".orb");
  const panel = root.querySelector(".panel");
  const input = root.querySelector("input");
  const micBtn = root.querySelector(".mic");
  const goBtn = root.querySelector(".go");
  const answerEl = root.querySelector(".answer");
  const whyEl = root.querySelector(".why");
  let pollTimer = null;

  orb.addEventListener("click", () => {
    panel.style.display = panel.style.display === "block" ? "none" : "block";
    if (panel.style.display === "block") input.focus();
  });

  function headers(extra) {
    const h = extra || {};
    if (apiKey) h["X-API-Key"] = apiKey;
    return h;
  }

  function speak(text, lang) {
    if (!("speechSynthesis" in window) || !text) return;
    const u = new SpeechSynthesisUtterance(text);
    if (lang) u.lang = lang;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  }

  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (Recognition) {
    micBtn.style.display = "block";
    const recognizer = new Recognition();
    recognizer.lang = document.documentElement.lang || navigator.language || "fr-FR";
    recognizer.onresult = (e) => { input.value = e.results[0][0].transcript; ask(); };
    recognizer.onend = () => { micBtn.textContent = "🎤"; };
    micBtn.addEventListener("click", () => { micBtn.textContent = "🔴"; recognizer.start(); });
  }

  async function ask() {
    const text = input.value.trim();
    if (!text) return;
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    answerEl.style.display = "block";
    answerEl.textContent = "…";
    whyEl.style.display = "none";
    try {
      const res = await fetch(base + "/v1/intent", {
        method: "POST",
        headers: headers({ "Content-Type": "application/json" }),
        body: JSON.stringify({ text }),
      });
      if (res.status === 401) throw new Error("clé API manquante ou invalide (data-axiomn-key)");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      const awaiting = data.action.type === "await_human";
      answerEl.textContent = awaiting ? "⏳ " + data.result : data.result;
      whyEl.textContent = "route: " + data.route + (data.model ? " · model: " + data.model : "")
        + " · " + data.execution_time_ms + " ms";
      whyEl.style.display = "block";
      if (data.action.type === "voice_reply") speak(data.result, data.language);
      if (awaiting && data.action.payload.status_url) {
        pollTimer = setInterval(async () => {
          try {
            const t = await (await fetch(base + data.action.payload.status_url, { headers: headers() })).json();
            if (t.status === "answered") {
              clearInterval(pollTimer);
              pollTimer = null;
              answerEl.textContent = "🧑‍🏫 " + t.answer;
              speak(t.answer, data.language);
            }
          } catch (_) { /* transient: keep polling */ }
        }, 2000);
      }
    } catch (err) {
      answerEl.textContent = "⚠ " + err.message;
    }
  }

  goBtn.addEventListener("click", ask);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") ask(); });
})();
