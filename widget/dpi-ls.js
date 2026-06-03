/* DPI-LS embeddable widget — vanilla web components, no framework.
 *
 * Usage on any host page:
 *   <script src="https://your-host/widget/dpi-ls.js" defer></script>
 *   <dpi-ls-board api-base="https://your-host" poll-interval="5000"></dpi-ls-board>
 *   <dpi-ls-agent agent-id="agent-strong-001" api-base="https://your-host"></dpi-ls-agent>
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
    R: "Reliability",
    V: "Validation",
    C: "Cost",
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
  `;

  const escapeHtml = (s) =>
    String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );

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
      <div class="card" part="card">
        <div class="head">
          <div>
            <div class="name">${escapeHtml(row.agent_name)}</div>
            <div class="id">${escapeHtml(row.agent_id)}</div>
          </div>
          ${bandPill(row.band)}
        </div>
        <div class="score">${fmtScore(row.score)}</div>
        ${row.unsafe ? `<div class="unsafe">⚠ Unsafe — compliance gate failed</div>` : ""}
        <div class="timestamp">${escapeHtml(fmtTime(row.computed_at))}</div>
      </div>
    `;
  }

  function metricLineHtml(key, value) {
    const label = METRIC_LABELS[key] || key;
    if (value === null || value === undefined) {
      return `<div class="metric">
        <span class="metric-label">${escapeHtml(label)}</span>
        <span class="metric-missing">SME</span>
      </div>`;
    }
    return `<div class="metric">
      <span class="metric-label">${escapeHtml(label)}</span>
      <span class="metric-value">${fmtMetric(value)}</span>
    </div>`;
  }

  function agentCardHtml(rating) {
    const metrics = ["P", "Q", "E", "G", "R", "V", "C"]
      .map((k) => metricLineHtml(k, rating.metrics ? rating.metrics[k] : null))
      .join("");
    const unsafeBanner = rating.unsafe
      ? `<div class="unsafe">⚠ Unsafe — failing gates: ${(rating.gate_failures || []).map(escapeHtml).join(", ") || "—"}</div>`
      : "";
    const missing = (rating.missing || []).length
      ? `<div class="missing-note">Pending SME input: ${rating.missing.map(escapeHtml).join(", ")}</div>`
      : "";
    return `
      <div class="card" part="card">
        <div class="head">
          <div class="score">${fmtScore(rating.score)}</div>
          ${bandPill(rating.band)}
        </div>
        ${unsafeBanner}
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
      return ["api-base", "poll-interval"];
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
    }
  }

  class DpiLsAgent extends Pollable {
    static get observedAttributes() {
      return ["agent-id", "api-base", "poll-interval"];
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
      else body = agentCardHtml(rating);
      this._renderShell(body);
    }
  }

  if (!customElements.get("dpi-ls-board")) {
    customElements.define("dpi-ls-board", DpiLsBoard);
  }
  if (!customElements.get("dpi-ls-agent")) {
    customElements.define("dpi-ls-agent", DpiLsAgent);
  }
})();
