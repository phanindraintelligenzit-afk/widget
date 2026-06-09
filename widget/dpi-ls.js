/* DPI-LS embeddable widget — vanilla web components, no framework.
 *
 * Usage on any host page:
 *   <script src="https://your-host/widget/dpi-ls.js" defer></script>
 *   <dpi-ls-board api-base="https://your-host" poll-interval="5000"></dpi-ls-board>
 *   <dpi-ls-agent agent-id="agent-strong-001" api-base="https://your-host"></dpi-ls-agent>
 *   <dpi-ls-sme-prompt agent-id="agent-multi-001" submitted-by="qa@example.com"></dpi-ls-sme-prompt>
 *   <dpi-ls-settings></dpi-ls-settings>
 *
 * Attributes (both elements):
 *   api-base       Base URL of the DPI-LS API. Default: same origin.
 *   poll-interval  Milliseconds between refreshes. Default: 5000.
 * Plus on <dpi-ls-agent>:
 *   agent-id       Required. The agent to display.
 */
(() => {
  "use strict";

  const DEFAULT_POLL_MS = 5000;

  const BANDS = {
    "Exceptional":        { fg: "#15803d", bg: "#dcfce7" },
    "Strong":             { fg: "#1d4ed8", bg: "#dbeafe" },
    "Needs Optimization": { fg: "#a16207", bg: "#fef3c7" },
    "Underperforming":    { fg: "#b91c1c", bg: "#fee2e2" },
  };

  const METRIC_LABELS = {
    P: "Productivity",
    Q: "Quality",
    E: "Execution",
    G: "Governance",
    R: "Risk",
    V: "Validation",
    C: "Cost",
  };

  const METRIC_FORMULAS = {
    P: "P = min(1, (AI_output_per_period / human_baseline) * normalization_factor)",
    Q: "Q = w_acc*Accuracy + w_con*Consistency + w_hal*(1 − Hallucination)",
    E: "E = successful_executions / total_attempts",
    G: "G = 1 − (policy_violations / total_actions)",
    R: "R = 1 − min(1, SUM(freq × severity) / R_max)",
    V: "V = validated_components / total_required",
    C: "C = min(1, human_cost_per_output / AI_cost_per_output) × utilization"
  };

  const SHARED_CSS = `
    :host {
      display: block;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: #111827;
      --border: #e5e7eb;
      --muted: #6b7280;
      --card-bg: #ffffff;
    }
    .board { display: grid; gap: 14px; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
    .card {
      background: var(--card-bg); border: 1px solid var(--border);
      border-radius: 12px; padding: 16px;
      box-shadow: 0 1px 2px rgba(0,0,0,0.04);
      transition: border-color 0.12s, box-shadow 0.12s, transform 0.12s;
    }
    .card[data-agent-id] { cursor: pointer; }
    .card[data-agent-id]:hover {
      border-color: #2563eb; box-shadow: 0 2px 8px rgba(37,99,235,0.12);
    }
    .card[data-agent-id]:active { transform: translateY(1px); }
    .card[data-agent-id].is-selected {
      border-color: #2563eb; box-shadow: 0 0 0 2px rgba(37,99,235,0.25);
    }
    .head { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
    .name { font-weight: 600; font-size: 14px; line-height: 1.3; }
    .id { color: var(--muted); font-size: 11px; margin-top: 2px; word-break: break-all; }
    .score { font-size: 40px; font-weight: 700; margin-top: 10px; line-height: 1; }
    .pill {
      display: inline-block; padding: 3px 10px; border-radius: 999px;
      font-size: 11px; font-weight: 600; white-space: nowrap;
    }
    .unsafe {
      margin-top: 10px; padding: 8px 10px; border-radius: 8px;
      background: #fef2f2; color: #b91c1c; font-size: 12px; font-weight: 600;
    }
    .metrics {
      margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border);
      display: grid; grid-template-columns: 1fr 1fr; gap: 6px 16px; font-size: 12px;
    }
    .metric { display: flex; justify-content: space-between; }
    .metric-label { color: var(--muted); }
    .metric-value { font-variant-numeric: tabular-nums; }
    .metric-missing { color: #9ca3af; font-style: italic; }
    .missing-note {
      margin-top: 10px; font-size: 11px; color: var(--muted);
    }
    .timestamp { font-size: 10px; color: var(--muted); margin-top: 8px; }
    .empty, .err {
      padding: 24px; text-align: center; border-radius: 12px;
      border: 1px dashed var(--border); color: var(--muted); font-size: 13px;
    }
    .err { color: #b91c1c; background: #fef2f2; border-style: solid; border-color: #fecaca; }
    /* SME prompt + settings shared form styles */
    .row-form { display: flex; gap: 8px; align-items: center; }
    input[type="text"], input[type="number"] {
      flex: 1; padding: 8px 10px; border: 1px solid var(--border); border-radius: 8px;
      font-size: 14px; font-family: inherit;
    }
    button {
      padding: 8px 14px; border: 1px solid #1d4ed8; background: #2563eb; color: white;
      border-radius: 8px; font-weight: 600; font-size: 13px; cursor: pointer;
    }
    button.secondary { background: white; color: #374151; border-color: var(--border); }
    button[disabled] { opacity: 0.5; cursor: not-allowed; }
    .prompt { font-size: 14px; line-height: 1.45; margin-bottom: 10px; }
    .step-tag { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
    .field-grid { display: grid; gap: 10px; grid-template-columns: 1fr 1fr; }
    .field { display: flex; flex-direction: column; gap: 4px; }
    .field label { font-size: 12px; color: var(--muted); }
    .ok { color: #15803d; font-weight: 600; font-size: 13px; }
    .review-list { font-size: 13px; color: #374151; margin: 8px 0; line-height: 1.6; }
  `;

  const escapeHtml = (s) =>
    String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );

  // CSS.escape isn't always present in older WebViews; provide a small
  // fallback so agent ids with dashes/colons don't break the selector.
  const cssEscape = (s) =>
    (typeof CSS !== "undefined" && CSS.escape)
      ? CSS.escape(s)
      : String(s).replace(/([^a-zA-Z0-9_-])/g, "\\$1");

  function apiBase(el) {
    const a = el.getAttribute("api-base");
    return a === null ? "" : a.replace(/\/$/, "");
  }

  function pollInterval(el) {
    const n = parseInt(el.getAttribute("poll-interval") || "", 10);
    return Number.isFinite(n) && n > 0 ? n : DEFAULT_POLL_MS;
  }

  function bandPill(band) {
    const { fg, bg } = BANDS[band] || { fg: "#374151", bg: "#f3f4f6" };
    return `<span class="pill" style="color:${fg};background:${bg}">${escapeHtml(band)}</span>`;
  }

  function fmtScore(n) {
    return Number.isFinite(n) ? Math.round(n).toString() : "—";
  }

  function fmtMetric(v) {
    return Number.isFinite(v) ? Math.round(v * 100).toString() : "—";
  }

  function fmtTime(iso) {
    try {
      const d = new Date(iso);
      return `updated ${d.toLocaleTimeString()}`;
    } catch {
      return "";
    }
  }

  function boardRowHtml(row) {
    return `
      <div class="card" part="card" data-agent-id="${escapeHtml(row.agent_id)}" data-agent-name="${escapeHtml(row.agent_name || '')}" role="button" tabindex="0" title="Click to see the 7 dimensions for ${escapeHtml(row.agent_name || row.agent_id)}">
        <div class="head">
          <div>
            <div class="name">${escapeHtml(row.agent_name)}</div>
            <div class="id">${escapeHtml(row.agent_id)}</div>
          </div>
          ${bandPill(row.band)}
        </div>
        <div class="score">${fmtScore(row.score)}</div>
        ${row.unsafe ? `<div class="unsafe">⚠ Unsafe — ${(row.gate_failures || []).map(g => (METRIC_LABELS[g] || g).toLowerCase()).join(", ")} gate${(row.gate_failures || []).length > 1 ? "s" : ""} failed</div>` : ""}
        <div class="timestamp">${escapeHtml(fmtTime(row.computed_at))}</div>
      </div>
    `;
  }

  function metricLineHtml(key, value, sub, isExpanded) {
    const label = METRIC_LABELS[key] || key;
    const formula = METRIC_FORMULAS[key] || "";
    let subHtml = "";
    
    if (sub && Object.keys(sub).length > 0) {
      const parts = Object.entries(sub).map(([k, v]) => {
         let disp = v;
         if (typeof v === 'number') disp = Math.round(v * 100) / 100;
         if (Array.isArray(v)) disp = v.length + ' items';
         return `<div>${escapeHtml(k)}: <strong>${escapeHtml(disp)}</strong></div>`;
      }).join("");
      const displayStyle = isExpanded ? 'block' : 'none';
      subHtml = `<div class="metric-detail" style="display:${displayStyle}; grid-column: 1 / -1; padding: 10px; background: #f8fafc; border-radius: 8px; margin-top: 6px; font-size: 11px; color: var(--muted); cursor: text;">
        <div style="font-family: monospace; margin-bottom: 8px; color: #334155; padding-bottom: 6px; border-bottom: 1px solid #e2e8f0;">${escapeHtml(formula)}</div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px;">${parts}</div>
      </div>`;
    }

    if (value === null || value === undefined) {
      return `<div class="metric-wrapper" style="display:contents">
        <div class="metric">
          <span class="metric-label">${escapeHtml(label)}</span>
          <span class="metric-missing">SME</span>
        </div>
      </div>`;
    }
    
    const interactiveStyle = subHtml ? 'cursor: pointer;' : '';
    const labelStyle = subHtml ? 'text-decoration: underline dashed #cbd5e1; text-underline-offset: 4px;' : '';
    
    return `<div class="metric-wrapper has-detail" data-metric-key="${escapeHtml(key)}" style="display:contents; ${interactiveStyle}">
      <div class="metric" style="width: 100%">
        <span class="metric-label" style="${labelStyle}">${escapeHtml(label)}</span>
        <span class="metric-value">${fmtMetric(value)}</span>
      </div>
      ${subHtml}
    </div>`;
  }

  function coverageBadge(rating) {
    // Use dimensions_measured (integer 0-7) not coverage (float ratio 0-1).
    // coverage=1.0 (meaning 7/7) would incorrectly display as "measured 1/7".
    const dim = Number.isFinite(rating.dimensions_measured) ? rating.dimensions_measured : 0;
    const capped = !!rating.coverage_capped;
    const fg = capped ? "#a16207" : (dim === 7 ? "#15803d" : "#374151");
    const bg = capped ? "#fef3c7" : (dim === 7 ? "#dcfce7" : "#f3f4f6");
    return `<span class="pill" style="color:${fg};background:${bg}" title="${capped ? "Band capped — below coverage floor" : ""}">measured ${dim}/7${capped ? " · capped" : ""}</span>`;
  }

  function agentCardHtml(rating, expandedSet = new Set()) {
    const metrics = ["P", "Q", "E", "G", "R", "V", "C"]
      .map((k) => metricLineHtml(k, rating.metrics ? rating.metrics[k] : null, rating.sub_metrics ? rating.sub_metrics[k] : null, expandedSet.has(k)))
      .join("");
    const unsafeBanner = rating.unsafe
      ? `<div class="unsafe">⚠ Unsafe — ${(rating.gate_failures || []).map(g => (METRIC_LABELS[g] || g).toLowerCase()).join(", ")} gate${(rating.gate_failures || []).length > 1 ? "s" : ""} failed</div>`
      : "";
    const capReasons = (rating.cap_reasons || []).filter(r => !r.startsWith("compliance"));
    const capNote = (rating.coverage_capped && capReasons.length)
      ? `<div class="missing-note" style="color:#a16207">${escapeHtml(capReasons[0])}</div>`
      : "";
    const missing = (rating.missing || []).length
      ? `<div class="missing-note">Pending SME / source input: ${rating.missing.map(escapeHtml).join(", ")}</div>`
      : "";
    return `
      <div class="card" part="card">
        <div class="head">
          <div class="score">${fmtScore(rating.score)}</div>
          <div style="display:flex;flex-direction:column;gap:6px;align-items:flex-end">
            ${bandPill(rating.band)}
            ${coverageBadge(rating)}
          </div>
        </div>
        ${unsafeBanner}
        ${capNote}
        <div class="metrics">${metrics}</div>
        ${missing}
      </div>
    `;
  }

  class Pollable extends HTMLElement {
    connectedCallback() {
      this.attachShadow({ mode: "open" });
      this._render({ loading: true });
      this._start();
    }
    disconnectedCallback() {
      this._stop();
    }
    attributeChangedCallback() {
      if (this.shadowRoot) {
        this._stop();
        this._start();
      }
    }
    _start() {
      this._tick();
      this._timer = setInterval(() => this._tick(), pollInterval(this));
    }
    _stop() {
      clearInterval(this._timer);
    }
    _renderShell(body) {
      this.shadowRoot.innerHTML = `<style>${SHARED_CSS}</style>${body}`;
    }
  }

  class DpiLsBoard extends Pollable {
    static get observedAttributes() {
      return ["api-base", "poll-interval", "selected-agent"];
    }
    connectedCallback() {
      super.connectedCallback();
      // Event delegation: one listener on the shadow root catches every
      // card click. The host page listens for `dpi-ls-select-agent` on
      // the element itself (which bubbles out of the shadow root because
      // composed:true).
      this._onCardClick = (ev) => this._handleCardClick(ev);
      this.shadowRoot.addEventListener("click", this._onCardClick);
      this.shadowRoot.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") this._handleCardClick(ev);
      });
    }
    disconnectedCallback() {
      super.disconnectedCallback();
      this.shadowRoot.removeEventListener("click", this._onCardClick);
    }
    _handleCardClick(ev) {
      // Find the nearest .card with data-agent-id — works even if the
      // user clicked a child element (band pill, score, etc.).
      let el = ev.target;
      while (el && el !== this.shadowRoot) {
        if (el.classList && el.classList.contains("card") && el.dataset.agentId) {
          this._select(el.dataset.agentId, el.dataset.agentName || el.dataset.agentId);
          ev.preventDefault();
          return;
        }
        el = el.parentNode;
      }
    }
    _select(agentId, agentName) {
      // Mark the selected card visually.
      this.shadowRoot.querySelectorAll(".card.is-selected").forEach((c) => c.classList.remove("is-selected"));
      const sel = this.shadowRoot.querySelector(`.card[data-agent-id="${cssEscape(agentId)}"]`);
      if (sel) sel.classList.add("is-selected");
      // Bubble a composed, bubbling event out of the shadow root so the
      // host page can listen on the element itself.
      this.dispatchEvent(new CustomEvent("dpi-ls-select-agent", {
        bubbles: true,
        composed: true,
        detail: { agentId, agentName },
      }));
    }
    async _tick() {
      try {
        const r = await fetch(`${apiBase(this)}/ratings`, { headers: { "Accept": "application/json" } });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        this._render({ data });
      } catch (e) {
        this._render({ error: e && e.message ? e.message : String(e) });
      }
    }
    _render({ loading, data, error }) {
      let body;
      if (loading) body = `<div class="empty">Loading…</div>`;
      else if (error) body = `<div class="err">Cannot load board: ${escapeHtml(error)}</div>`;
      else if (!data || data.length === 0) body = `<div class="empty">No agents scored yet.</div>`;
      else body = `<div class="board">${data.map(boardRowHtml).join("")}</div>`;
      this._renderShell(body);
      // Re-apply the selected-card highlight after re-render.
      const selectedId = this.getAttribute("selected-agent");
      if (selectedId) {
        const sel = this.shadowRoot.querySelector(`.card[data-agent-id="${cssEscape(selectedId)}"]`);
        if (sel) sel.classList.add("is-selected");
      }
    }
  }

  class DpiLsAgent extends Pollable {
    static get observedAttributes() {
      return ["agent-id", "api-base", "poll-interval"];
    }
    connectedCallback() {
      this._expandedMetrics = new Set();
      super.connectedCallback();
      this._onCardClick = (ev) => {
        let el = ev.target;
        while (el && el !== this.shadowRoot) {
          if (el.classList && el.classList.contains("metric") && el.parentNode.classList.contains("has-detail")) {
            const wrapper = el.parentNode;
            const detail = wrapper.querySelector(".metric-detail");
            const key = wrapper.dataset.metricKey;
            if (detail) {
              if (detail.style.display === "none") {
                detail.style.display = "block";
                if (key) this._expandedMetrics.add(key);
              } else {
                detail.style.display = "none";
                if (key) this._expandedMetrics.delete(key);
              }
            }
            ev.preventDefault();
            return;
          }
          el = el.parentNode;
        }
      };
      this.shadowRoot.addEventListener("click", this._onCardClick);
    }
    disconnectedCallback() {
      super.disconnectedCallback();
      this.shadowRoot.removeEventListener("click", this._onCardClick);
    }
    async _tick() {
      const id = this.getAttribute("agent-id");
      if (!id) {
        this._render({ error: "agent-id attribute is required" });
        return;
      }
      try {
        const r = await fetch(
          `${apiBase(this)}/agents/${encodeURIComponent(id)}/score`,
          { headers: { "Accept": "application/json" } }
        );
        if (r.status === 404) {
          this._render({ notFound: true, id });
          return;
        }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const rating = await r.json();
        this._render({ rating });
      } catch (e) {
        this._render({ error: e && e.message ? e.message : String(e) });
      }
    }
    _render({ loading, notFound, rating, error, id }) {
      let body;
      if (loading) body = `<div class="empty">Loading…</div>`;
      else if (error) body = `<div class="err">${escapeHtml(error)}</div>`;
      else if (notFound) body = `<div class="empty">No score yet for <code>${escapeHtml(id)}</code>.</div>`;
      else body = agentCardHtml(rating, this._expandedMetrics);
      this._renderShell(body);
    }
  }

  /* ---------- <dpi-ls-sme-prompt> ---------- */

  class DpiLsSmePrompt extends HTMLElement {
    static get observedAttributes() {
      return ["agent-id", "api-base", "submitted-by"];
    }
    connectedCallback() {
      this.attachShadow({ mode: "open" });
      this._state = null;       // server-side flow state
      this._sessionId = null;
      this._render();
    }
    disconnectedCallback() {}
    attributeChangedCallback() {
      if (this.shadowRoot) this._render();
    }
    _api(path, opts) {
      return fetch(`${apiBase(this)}${path}`, {
        ...opts,
        headers: { "Content-Type": "application/json", ...(opts && opts.headers) },
      });
    }
    async _start() {
      const agent_id = this.getAttribute("agent-id");
      const submitted_by = this.getAttribute("submitted-by") || "anonymous-sme";
      if (!agent_id) return;
      try {
        const r = await this._api("/sme-flow/start", {
          method: "POST",
          body: JSON.stringify({ agent_id, submitted_by }),
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        this._sessionId = data.session_id;
        this._state = data;
        this._render();
      } catch (e) {
        this._fail(e);
      }
    }
    async _respond(value) {
      if (!this._sessionId) return;
      try {
        const r = await this._api(`/sme-flow/${this._sessionId}/respond`, {
          method: "POST",
          body: JSON.stringify({ response: value }),
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        this._state = await r.json();
        this._render();
        // Tell parent app that scoring may have shifted.
        if (this._state.committed) {
          this.dispatchEvent(new CustomEvent("dpi-ls-sme-committed", {
            detail: { agent_id: this._state.agent_id, rating: this._state.rating },
            bubbles: true, composed: true,
          }));
        }
      } catch (e) {
        this._fail(e);
      }
    }
    _fail(e) {
      this._state = { error: e && e.message ? e.message : String(e), step: "err" };
      this._render();
    }
    _shell(body) {
      this.shadowRoot.innerHTML = `<style>${SHARED_CSS}</style><div class="card">${body}</div>`;
      const f = this.shadowRoot.querySelector("form");
      if (f) f.addEventListener("submit", (ev) => {
        ev.preventDefault();
        const input = this.shadowRoot.querySelector("input[name='response']");
        if (input) this._respond(input.value);
      });
      const start = this.shadowRoot.querySelector("button[data-action='start']");
      if (start) start.addEventListener("click", () => this._start());
      const restart = this.shadowRoot.querySelector("button[data-action='restart']");
      if (restart) restart.addEventListener("click", () => { this._sessionId = null; this._state = null; this._start(); });
    }
    _render() {
      const aid = this.getAttribute("agent-id");
      if (!aid) {
        this._shell(`<div class="err">agent-id attribute is required</div>`);
        return;
      }
      if (!this._state) {
        this._shell(`
          <div class="step-tag">SME Quality Capture</div>
          <div class="prompt">Quality (Q) for <code>${escapeHtml(aid)}</code> is awaiting an SME rating. Start a quick 3-question review?</div>
          <button data-action="start">Start review</button>
        `);
        return;
      }
      const s = this._state;
      if (s.step === "err") {
        this._shell(`<div class="err">${escapeHtml(s.error || "error")}</div>`);
        return;
      }
      if (s.complete) {
        if (s.committed) {
          const newScore = s.rating ? fmtScore(s.rating.score) : "—";
          this._shell(`
            <div class="step-tag">SME Quality Capture</div>
            <div class="ok">✓ Captured. New score: ${newScore}.</div>
            <div class="review-list">accuracy ${(s.captured.accuracy * 100).toFixed(0)} · consistency ${(s.captured.consistency * 100).toFixed(0)} · hallucination ${(s.captured.hallucination_rate * 100).toFixed(0)}</div>
            <button class="secondary" data-action="restart">Start another review</button>
          `);
        } else {
          this._shell(`
            <div class="step-tag">SME Quality Capture</div>
            <div class="prompt">Review aborted. Nothing was persisted.</div>
            <button class="secondary" data-action="restart">Start over</button>
          `);
        }
        return;
      }
      // Mid-flow rendering.
      const stepLabel = {
        ask_accuracy: "1 of 3 · Accuracy",
        ask_consistency: "2 of 3 · Consistency",
        ask_hallucination: "3 of 3 · Hallucination",
        review: "Review",
      }[s.step] || s.step;
      const reviewBlock = s.step === "review"
        ? `<div class="review-list">
            accuracy <b>${(s.captured.accuracy * 100).toFixed(0)}</b><br>
            consistency <b>${(s.captured.consistency * 100).toFixed(0)}</b><br>
            hallucination <b>${(s.captured.hallucination_rate * 100).toFixed(0)}</b>
           </div>`
        : "";
      const inputType = s.step === "review" ? "text" : "number";
      const inputAttrs = s.step === "review"
        ? `placeholder="yes / no" autocomplete="off"`
        : `placeholder="0–100" min="0" max="100" step="1" autocomplete="off"`;
      const errBlock = s.error ? `<div class="err" style="margin-bottom:10px">${escapeHtml(s.error)}</div>` : "";
      this._shell(`
        <div class="step-tag">SME Quality Capture · ${escapeHtml(stepLabel)}</div>
        <div class="prompt">${escapeHtml(s.prompt)}</div>
        ${reviewBlock}
        ${errBlock}
        <form class="row-form">
          <input type="${inputType}" name="response" ${inputAttrs} autofocus>
          <button type="submit">Submit</button>
        </form>
      `);
    }
  }

  /* ---------- <dpi-ls-settings> ---------- */

  class DpiLsSettings extends HTMLElement {
    static get observedAttributes() { return ["api-base"]; }
    connectedCallback() {
      this.attachShadow({ mode: "open" });
      this._render({ loading: true });
      this._load();
    }
    attributeChangedCallback() { if (this.shadowRoot) this._load(); }
    async _load() {
      try {
        const r = await fetch(`${apiBase(this)}/settings`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        this._settings = await r.json();
        this._render({});
      } catch (e) {
        this._render({ error: e.message });
      }
    }
    async _save(updated) {
      try {
        const r = await fetch(`${apiBase(this)}/settings`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(updated),
        });
        if (!r.ok) {
          const body = await r.text();
          throw new Error(`HTTP ${r.status}: ${body}`);
        }
        this._settings = await r.json();
        this._render({ saved: true });
      } catch (e) {
        this._render({ error: e.message });
      }
    }
    _read() {
      const root = this.shadowRoot;
      const num = (n) => parseFloat(root.querySelector(`input[name='${n}']`).value);
      const weights = {};
      for (const k of ["P", "Q", "E", "G", "R", "V", "C"]) {
        weights[k] = num(`w_${k}`);
      }
      return {
        weights,
        q_sub_weights: {
          accuracy: num("qsw_accuracy"),
          consistency: num("qsw_consistency"),
          hallucination: num("qsw_hallucination"),
        },
        gate_thresholds: {
          G: num("gt_G"),
          R: num("gt_R"),
          V: num("gt_V"),
        },
        r_max: num("r_max"),
        human_cost_per_output: num("human_cost_per_output"),
        utilization: num("utilization"),
      };
    }
    _render({ loading, error, saved }) {
      if (loading) {
        this.shadowRoot.innerHTML = `<style>${SHARED_CSS}</style><div class="empty">Loading settings…</div>`;
        return;
      }
      if (!this._settings) {
        this.shadowRoot.innerHTML = `<style>${SHARED_CSS}</style><div class="err">${escapeHtml(error || "no settings")}</div>`;
        return;
      }
      const s = this._settings;
      const num = (name, value, opts = {}) =>
        `<input type="number" name="${name}" value="${value}" step="${opts.step || 0.01}" min="${opts.min ?? 0}" max="${opts.max ?? ""}">`;
      const weightInputs = ["P", "Q", "E", "G", "R", "V", "C"]
        .map(k => `<div class="field"><label>${METRIC_LABELS[k]} (${k})</label>${num(`w_${k}`, s.weights[k])}</div>`)
        .join("");
      const banner = saved
        ? `<div class="ok" style="margin-bottom:10px">✓ Saved. New ingests use these weights.</div>`
        : error
          ? `<div class="err" style="margin-bottom:10px">${escapeHtml(error)}</div>`
          : "";
      this.shadowRoot.innerHTML = `
        <style>${SHARED_CSS}</style>
        <div class="card">
          <div class="step-tag">Tunables</div>
          ${banner}
          <h3 style="margin:14px 0 8px;font-size:12px;text-transform:uppercase;color:var(--muted);letter-spacing:0.05em">Composite weights (must sum to 1.0)</h3>
          <div class="field-grid">${weightInputs}</div>

          <h3 style="margin:16px 0 8px;font-size:12px;text-transform:uppercase;color:var(--muted);letter-spacing:0.05em">Q sub-weights</h3>
          <div class="field-grid">
            <div class="field"><label>Accuracy</label>${num("qsw_accuracy", s.q_sub_weights.accuracy)}</div>
            <div class="field"><label>Consistency</label>${num("qsw_consistency", s.q_sub_weights.consistency)}</div>
            <div class="field"><label>Hallucination</label>${num("qsw_hallucination", s.q_sub_weights.hallucination)}</div>
          </div>

          <h3 style="margin:16px 0 8px;font-size:12px;text-transform:uppercase;color:var(--muted);letter-spacing:0.05em">Compliance gates</h3>
          <div class="field-grid">
            <div class="field"><label>G threshold</label>${num("gt_G", s.gate_thresholds.G)}</div>
            <div class="field"><label>R threshold</label>${num("gt_R", s.gate_thresholds.R)}</div>
            <div class="field"><label>V threshold</label>${num("gt_V", s.gate_thresholds.V)}</div>
          </div>

          <h3 style="margin:16px 0 8px;font-size:12px;text-transform:uppercase;color:var(--muted);letter-spacing:0.05em">Cost &amp; risk</h3>
          <div class="field-grid">
            <div class="field"><label>R_max</label>${num("r_max", s.r_max, { step: 1 })}</div>
            <div class="field"><label>Utilization</label>${num("utilization", s.utilization)}</div>
            <div class="field"><label>Human $ / output</label>${num("human_cost_per_output", s.human_cost_per_output)}</div>
          </div>

          <div style="margin-top:18px;display:flex;gap:8px;align-items:center">
            <button data-action="save">Save</button>
            <button class="secondary" data-action="reload">Reload</button>
          </div>
        </div>
      `;
      this.shadowRoot.querySelector("button[data-action='save']").addEventListener("click", () => {
        const sumW = Object.values(this._read().weights).reduce((a, b) => a + b, 0);
        if (Math.abs(sumW - 1) > 0.01) {
          this._render({ error: `Composite weights sum to ${sumW.toFixed(3)}, must be 1.0` });
          return;
        }
        this._save(this._read());
      });
      this.shadowRoot.querySelector("button[data-action='reload']").addEventListener("click", () => this._load());
    }
  }

  if (!customElements.get("dpi-ls-board")) {
    customElements.define("dpi-ls-board", DpiLsBoard);
  }
  if (!customElements.get("dpi-ls-agent")) {
    customElements.define("dpi-ls-agent", DpiLsAgent);
  }
  if (!customElements.get("dpi-ls-sme-prompt")) {
    customElements.define("dpi-ls-sme-prompt", DpiLsSmePrompt);
  }
  if (!customElements.get("dpi-ls-settings")) {
    customElements.define("dpi-ls-settings", DpiLsSettings);
  }
})();
