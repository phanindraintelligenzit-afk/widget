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
    P: "Productivity (15%)",
    Q: "Quality (20%)",
    E: "Execution (15%)",
    G: "Governance (20%)",
    R: "Risk (15%)",
    V: "Validation (10%)",
    C: "Cost (5%)",
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

  function bandForScore(score, fallback) {
    if (!Number.isFinite(score)) return fallback;
    if (score >= 85) return "Exceptional";
    if (score >= 70) return "Strong";
    if (score >= 50) return "Needs Optimization";
    return "Underperforming";
  }

  function bandPill(band) {
    const { fg, bg } = BANDS[band] || { fg: "#374151", bg: "#f3f4f6" };
    return `<span class="pill" style="color:${fg};background:${bg}">${escapeHtml(band)}</span>`;
  }

  function fmtScore(n) {
    return Number.isFinite(n) ? (Number.isInteger(n) ? n.toString() : n.toFixed(1)) : "—";
  }

  function fmtMetric(v) {
    // Display the metric as a percentage — the natural reading.
    // The total score is the weighted sum of the 7 metric percentages
    // (see ``engine.score.composite``), so the user can do the math
    // mentally: 100% × 0.15 + 82.5% × 0.20 + … = raw_score.
    return Number.isFinite(v) ? Math.round(v * 100).toString() : "—";
  }

  function fmtWeightedMetric(v, weightPercent) {
    // Weighted contribution to the raw score (value × weightPercent).
    // Surfaced in the metric detail panel so the user can see exactly
    // what each dim adds up to.
    if (!Number.isFinite(v)) return "—";
    const val = v * weightPercent;
    return val.toFixed(2);
  }

  function fmtTime(iso) {
    try {
      const d = new Date(iso);
      return `updated ${d.toLocaleTimeString()}`;
    } catch {
      return "";
    }
  }


  function getScoreColor(score) {
    if (score === null || score === undefined) return '#38bdf8';
    if (score >= 80) return '#10b981';
    if (score > 50) return '#facc15';
    return '#ef4444';
  }

  function boardRowHtml(row) {
    if (!row) return "";
    const w_m = row.weighted_metrics || {};
    const KEYS = ["P", "Q", "E", "G", "R", "V", "C"];
    
    const scoreToUse = row.raw_score !== null && row.raw_score !== undefined ? row.raw_score : row.score;
    let sum = 0;
    const metricCells = KEYS.map(k => {
      if (w_m[k] !== null && w_m[k] !== undefined) {
        sum += (w_m[k] * 100);
      }
      const display = (w_m[k] !== null && w_m[k] !== undefined)
        ? (w_m[k] * 100).toFixed(2)
        : "\u2014";
      return `<td class="metric-cell" data-key="${k}" style="padding:8px 12px;border:1px solid #1e293b;color:#4ade80;text-align:center;cursor:pointer;font-weight:600;" title="Click to see ${METRIC_LABELS[k] || k} details">${display}</td>`;
    }).join("");
    
    return `
      <tr class="agent-row" data-agent-id="${escapeHtml(row.agent_id)}" data-agent-name="${escapeHtml(row.agent_name || row.agent_id)}" tabindex="0" role="row" style="background:#0f172a;transition:background 0.2s;">
        <td style="padding:10px 14px;border:1px solid #1e293b;color:#38bdf8;font-weight:700;white-space:nowrap;"><a href="/widget/agent-profile.html?id=${encodeURIComponent(row.agent_id)}" target="_blank" style="color:#38bdf8;text-decoration:underline;" onclick="event.stopPropagation();">${escapeHtml(row.agent_name || row.agent_id)}</a></td>
        <td style="padding:10px 14px;border:1px solid #1e293b;color:#facc15;font-weight:800;text-align:center;font-size:15px;" title="Sum of Parameters">${sum.toFixed(1)}</td>
        <td style="padding:10px 14px;border:1px solid #1e293b;color:${getScoreColor(scoreToUse)};font-weight:800;text-align:center;font-size:15px;" title="Official Evaluated DPI-LS Score">${fmtScore(scoreToUse)}</td>
        ${metricCells}
      </tr>
    `;
  }

  function calculateCostMetrics(sub, settings, value) {
    sub = sub || {};
    settings = settings || {};
    
    const getNum = (obj, key, fallback) => {
      if (obj && obj[key] !== undefined && obj[key] !== null && obj[key] !== "") {
        const val = parseFloat(obj[key]);
        if (!isNaN(val)) return val;
      }
      return fallback !== undefined ? fallback : null;
    };

    const inputTokens = getNum(sub, 'input_tokens');
    const outputTokens = getNum(sub, 'output_tokens');
    
    const inputTokenPrice = getNum(sub, 'input_token_price', getNum(settings, 'input_token_price'));
    const outputTokenPrice = getNum(sub, 'output_token_price', getNum(settings, 'output_token_price'));
    const completedOutputs = getNum(sub, 'completed_outputs', 1);
    const utilization = getNum(sub, 'utilization', getNum(settings, 'utilization'));
    const humanCostPerOutput = getNum(sub, 'Human Cost / Output', getNum(settings, 'human_cost_per_output'));
    
    const promptCost = getNum(sub, 'Prompt Cost (USD)', (inputTokens !== null && inputTokenPrice !== null ? inputTokens * inputTokenPrice : null));
    const completionCost = getNum(sub, 'Completion Cost (USD)', (outputTokens !== null && outputTokenPrice !== null ? outputTokens * outputTokenPrice : null));
    const modelCost = getNum(sub, 'Model Cost (USD)', (promptCost !== null && completionCost !== null ? promptCost + completionCost : null));
    const aiCostPerOutput = getNum(sub, 'AI Cost Per Output', (modelCost !== null && completedOutputs ? modelCost / completedOutputs : null));
    const efficiencyRatio = getNum(sub, 'Efficiency Ratio', (humanCostPerOutput !== null && aiCostPerOutput ? humanCostPerOutput / aiCostPerOutput : null));
    const tco = getNum(sub, 'Total Cost (USD)', (humanCostPerOutput !== null && modelCost !== null ? humanCostPerOutput + modelCost : null));

    // Calculate dynamic values
    const calcPromptCost = (inputTokens !== null && inputTokenPrice !== null) ? inputTokens * inputTokenPrice : null;
    const calcCompletionCost = (outputTokens !== null && outputTokenPrice !== null) ? outputTokens * outputTokenPrice : null;
    const calcModelCost = (calcPromptCost !== null && calcCompletionCost !== null) ? calcPromptCost + calcCompletionCost : null;
    const calcAiCostPerOutput = (calcModelCost !== null && completedOutputs) ? calcModelCost / completedOutputs : null;
    const calcEfficiencyRatio = (humanCostPerOutput !== null && calcAiCostPerOutput) ? humanCostPerOutput / calcAiCostPerOutput : null;
    
    let calcCostScore = null;
    if (humanCostPerOutput !== null && calcAiCostPerOutput !== null && utilization !== null) {
      const ratio = calcAiCostPerOutput > 0 ? Math.min(1.0, humanCostPerOutput / calcAiCostPerOutput) : 1.0;
      calcCostScore = ratio * utilization;
    }
    const calcTco = (humanCostPerOutput !== null && calcModelCost !== null) ? humanCostPerOutput + calcModelCost : null;

    let metricsMap = {
      input_tokens: { val: inputTokens, calc: inputTokens, disp: inputTokens, formula: "Langfuse Trace Payload", src: "Langfuse (runtime telemetry)", resource: "Langfuse", dec: 0 },
      output_tokens: { val: outputTokens, calc: outputTokens, disp: outputTokens, formula: "Langfuse Trace Payload", src: "Langfuse (runtime telemetry)", resource: "Langfuse", dec: 0 },
      prompt_cost: { val: promptCost, calc: calcPromptCost, disp: promptCost, formula: "Input Tokens × Price", src: "Langfuse (runtime telemetry)", resource: "Langfuse", dec: 6 },
      completion_cost: { val: completionCost, calc: calcCompletionCost, disp: completionCost, formula: "Output Tokens × Price", src: "Langfuse (runtime telemetry)", resource: "Langfuse", dec: 6 },
      model_cost: { val: modelCost, calc: calcModelCost, disp: modelCost, formula: "Prompt Cost + Completion Cost", src: "Langfuse (runtime telemetry)", resource: "Langfuse", dec: 6 },
      ai_cost_per_output: { val: aiCostPerOutput, calc: calcAiCostPerOutput, disp: aiCostPerOutput, formula: "Model Cost ÷ Outputs", src: "Prometheus (runtime telemetry)", resource: "Prometheus", dec: 6 },
      human_cost_per_output: { val: humanCostPerOutput, calc: humanCostPerOutput, disp: humanCostPerOutput, formula: "Config Baseline", src: "Grafana (runtime settings)", resource: "Grafana", dec: 0 },
      utilization: { val: utilization, calc: utilization, disp: utilization, formula: "Runtime Usage", src: "Prometheus (runtime telemetry)", resource: "Prometheus", dec: 0 },
      efficiency_ratio: { val: efficiencyRatio, calc: calcEfficiencyRatio, disp: efficiencyRatio, formula: "Human ÷ AI Cost", src: "Grafana (runtime settings)", resource: "Grafana", dec: 2 },
      cost_score: { val: calcCostScore, calc: calcCostScore, disp: calcCostScore, formula: "min(1, Human ÷ AI) × Utilization", src: "Grafana (runtime settings)", resource: "Grafana", dec: 6 },
      tco: { val: tco, calc: calcTco, disp: tco, formula: "Human Cost + Model Cost", src: "Grafana (runtime settings)", resource: "Grafana", dec: 6 }
    };

    // Dynamically append OpenLIT and OpenCost metrics
    for (const [key, val] of Object.entries(sub)) {
      if (key.startsWith("OpenLIT:") || key.startsWith("OpenCost:")) {
        const parts = key.split(":");
        const resourceName = parts[0];
        const metricName = parts[1];
        
        let numericVal = parseFloat(val);
        let finalVal = isNaN(numericVal) ? val : numericVal;
        
        // Ensure dollar signs are preserved if it's a string
        if (typeof val === "string" && val.startsWith("$")) {
          finalVal = val;
        }

        metricsMap[metricName] = {
          val: finalVal,
          calc: finalVal,
          disp: finalVal,
          formula: "Runtime Ingestion",
          src: `${resourceName} (runtime telemetry)`,
          resource: resourceName,
          dec: (typeof finalVal === "number") ? 4 : 0
        };
      }
    }
    
    return metricsMap;
  }

  function calculateValidationMetrics(sub, settings, value) {
    sub = sub || {};
    settings = settings || {};
    
    const req = sub["Required Components"] !== undefined ? sub["Required Components"] : 0;
    const val = sub["Validated Components"] !== undefined ? sub["Validated Components"] : 0;
    let calcVScore = 0;
    if (req > 0) {
      calcVScore = Math.min(1.0, val / req);
    }
    const vScoreVal = calcVScore;


    const traceId = sub.trace_id || "Unavailable";
    const spanCount = sub.span_count || "Unavailable";
    const latency = sub.latency || "Unavailable";
    const executionTime = sub.execution_time || "Unavailable";
    const dependencies = sub.dependencies || "Unavailable";
    const requestDuration = sub.request_duration || "Unavailable";
    const errorCount = sub.error_count || "Unavailable";
    const validationTraces = sub.validation_traces || "Unavailable";

    const traceTimeline = sub.trace_timeline || "Unavailable";
    const spanTimeline = sub.span_timeline || "Unavailable";
    const serviceCalls = sub.service_calls || "Unavailable";
    const requestPath = sub.request_path || "Unavailable";
    const traceLatency = sub.trace_latency || "Unavailable";
    const executionTimeline = sub.execution_timeline || "Unavailable";
    const errorTimeline = sub.error_timeline || "Unavailable";

    return {
      answer_relevancy: { val: sub.answer_relevancy || "Unavailable", calc: sub.answer_relevancy || "Unavailable", disp: sub.answer_relevancy || "Unavailable", formula: "Answer Relevancy Score", src: "DeepEval", resource: "DeepEval", dec: 3 },
      faithfulness: { val: sub.faithfulness || "Unavailable", calc: sub.faithfulness || "Unavailable", disp: sub.faithfulness || "Unavailable", formula: "Faithfulness Score", src: "DeepEval", resource: "DeepEval", dec: 3 },
      hallucination: { val: sub.hallucination || "Unavailable", calc: sub.hallucination || "Unavailable", disp: sub.hallucination || "Unavailable", formula: "Hallucination Score", src: "DeepEval", resource: "DeepEval", dec: 3 },
      correctness: { val: sub.correctness || "Unavailable", calc: sub.correctness || "Unavailable", disp: sub.correctness || "Unavailable", formula: "Correctness Score", src: "DeepEval", resource: "DeepEval", dec: 3 },
      evaluation_status: { val: sub.evaluation_status || "Unavailable", calc: sub.evaluation_status || "Unavailable", disp: sub.evaluation_status || "Unavailable", formula: "Evaluation Status", src: "DeepEval", resource: "DeepEval", dec: 0 },
      evaluation_count: { val: sub.evaluation_count || "Unavailable", calc: sub.evaluation_count || "Unavailable", disp: sub.evaluation_count || "Unavailable", formula: "Evaluation Count", src: "DeepEval", resource: "DeepEval", dec: 0 },

      trace_id: { val: traceId, calc: traceId, disp: traceId, formula: "Active Trace ID", src: "Jaeger Registry", resource: "Jaeger", dec: 0 },
      validation_traces: { val: validationTraces, calc: validationTraces, disp: validationTraces, formula: "Runtime Trace Count", src: "Jaeger Dashboard", resource: "Jaeger", dec: 0 },
      span_count: { val: spanCount, calc: spanCount, disp: spanCount, formula: "Span Count", src: "Jaeger Dashboard", resource: "Jaeger", dec: 0 },
      latency: { val: latency, calc: latency, disp: latency, formula: "Latency", src: "Jaeger Dashboard", resource: "Jaeger", dec: 0 },
      execution_time: { val: executionTime, calc: executionTime, disp: executionTime, formula: "Execution Time", src: "Jaeger Dashboard", resource: "Jaeger", dec: 0 },
      dependencies: { val: dependencies, calc: dependencies, disp: dependencies, formula: "Dependency Graph", src: "Jaeger Dashboard", resource: "Jaeger", dec: 0 },
      request_duration: { val: requestDuration, calc: requestDuration, disp: requestDuration, formula: "Request Duration", src: "Jaeger Dashboard", resource: "Jaeger", dec: 0 },
      error_count: { val: errorCount, calc: errorCount, disp: errorCount, formula: "Error Count", src: "Jaeger Dashboard", resource: "Jaeger", dec: 0 },
      structural_validation: { val: sub.structural_validation || "Unavailable", calc: sub.structural_validation || "Unavailable", disp: sub.structural_validation || "Unavailable", formula: "Structural Validation", src: "Guardrails AI", resource: "Guardrails AI", dec: 0 },
      schema_enforcement: { val: sub.schema_enforcement || "Unavailable", calc: sub.schema_enforcement || "Unavailable", disp: sub.schema_enforcement || "Unavailable", formula: "Schema Enforcement", src: "Guardrails AI", resource: "Guardrails AI", dec: 0 },
      guardrails_passed: { val: sub.guardrails_passed || "Unavailable", calc: sub.guardrails_passed || "Unavailable", disp: sub.guardrails_passed || "Unavailable", formula: "Passed Count", src: "Guardrails AI", resource: "Guardrails AI", dec: 0 },
      guardrails_failed: { val: sub.guardrails_failed || "Unavailable", calc: sub.guardrails_failed || "Unavailable", disp: sub.guardrails_failed || "Unavailable", formula: "Failed Count", src: "Guardrails AI", resource: "Guardrails AI", dec: 0 },
      
      type_safe_parsing: { val: sub.type_safe_parsing || "Unavailable", calc: sub.type_safe_parsing || "Unavailable", disp: sub.type_safe_parsing || "Unavailable", formula: "Type-Safe Parsing", src: "Pydantic AI", resource: "Pydantic AI", dec: 0 },
      validation_errors: { val: sub.validation_errors || "Unavailable", calc: sub.validation_errors || "Unavailable", disp: sub.validation_errors || "Unavailable", formula: "Validation Errors", src: "Pydantic AI", resource: "Pydantic AI", dec: 0 },
      schema_validation: { val: sub.schema_validation || "Unavailable", calc: sub.schema_validation || "Unavailable", disp: sub.schema_validation || "Unavailable", formula: "Schema Validation", src: "Pydantic AI", resource: "Pydantic AI", dec: 0 },
      
      structured_output_validation: { val: sub.structured_output_validation || "Unavailable", calc: sub.structured_output_validation || "Unavailable", disp: sub.structured_output_validation || "Unavailable", formula: "Output Validation", src: "Instructor", resource: "Instructor", dec: 0 },
      schema_mapping: { val: sub.schema_mapping || "Unavailable", calc: sub.schema_mapping || "Unavailable", disp: sub.schema_mapping || "Unavailable", formula: "Schema Mapping", src: "Instructor", resource: "Instructor", dec: 0 },
      instructor_passed: { val: sub.instructor_passed || "Unavailable", calc: sub.instructor_passed || "Unavailable", disp: sub.instructor_passed || "Unavailable", formula: "Passed Check", src: "Instructor", resource: "Instructor", dec: 0 },


      trace_timeline: { val: traceTimeline, calc: traceTimeline, disp: traceTimeline, formula: "Trace Timeline", src: "Zipkin Dashboard", resource: "Zipkin", dec: 0 },
      span_timeline: { val: spanTimeline, calc: spanTimeline, disp: spanTimeline, formula: "Span Timeline", src: "Zipkin Dashboard", resource: "Zipkin", dec: 0 },
      service_calls: { val: serviceCalls, calc: serviceCalls, disp: serviceCalls, formula: "Service Calls", src: "Zipkin Dashboard", resource: "Zipkin", dec: 0 },
      request_path: { val: requestPath, calc: requestPath, disp: requestPath, formula: "Request Path", src: "Zipkin Dashboard", resource: "Zipkin", dec: 0 },
      trace_latency: { val: traceLatency, calc: traceLatency, disp: traceLatency, formula: "Trace Latency", src: "Zipkin Dashboard", resource: "Zipkin", dec: 0 },
      execution_timeline: { val: executionTimeline, calc: executionTimeline, disp: executionTimeline, formula: "Execution Timeline", src: "Zipkin Dashboard", resource: "Zipkin", dec: 0 },
      error_timeline: { val: errorTimeline, calc: errorTimeline, disp: errorTimeline, formula: "Error Timeline", src: "Zipkin Dashboard", resource: "Zipkin", dec: 0 },

      Required_Components: { val: req, calc: req, disp: req, formula: "Count of Expected Metrics", src: "Validation Service (runtime telemetry)", resource: "Dynamic Calculation", dec: 0 },
      Validated_Components: { val: val, calc: val, disp: val, formula: "Count of SUCCESS Metrics", src: "Validation Service (runtime telemetry)", resource: "Dynamic Calculation", dec: 0 },
      Validation_Score: { val: vScoreVal, calc: calcVScore, disp: vScoreVal, formula: "Validated Components / Required Components", src: "Validation Service (runtime telemetry)", resource: "Dynamic Calculation", dec: 4 },
    };
  }

  function calculateQualityMetrics(sub, settings, value) {
    sub = sub || {};
    settings = settings || {};
    
    const accuracy = sub.semantic_accuracy || "Unavailable";
    const consistency = sub.consistency_measurement || "Unavailable";
    const hallucination = sub.hallucination_analysis || "Unavailable";
    
    let qScoreVal = "Pending SME Review";
    if (value !== undefined && value !== null && value !== "Pending SME Review") {
      qScoreVal = value;
    }

    return {
      runtime_traces: { val: sub.runtime_traces || "Unavailable", calc: sub.runtime_traces || "Unavailable", disp: sub.runtime_traces || "Unavailable", formula: "Runtime Traces", src: "LangSmith", resource: "LangSmith", dec: 0 },
      llm_evaluation: { val: sub.llm_evaluation || "Unavailable", calc: sub.llm_evaluation || "Unavailable", disp: sub.llm_evaluation || "Unavailable", formula: "LLM Evaluation Score", src: "LangSmith", resource: "LangSmith", dec: 3 },
      hallucination_analysis: { val: sub.hallucination_analysis || "Unavailable", calc: sub.hallucination_analysis || "Unavailable", disp: sub.hallucination_analysis || "Unavailable", formula: "Hallucination Rate", src: "LangSmith", resource: "LangSmith", dec: 3 },
      prompt_evaluation: { val: sub.prompt_evaluation || "Unavailable", calc: sub.prompt_evaluation || "Unavailable", disp: sub.prompt_evaluation || "Unavailable", formula: "Prompt Evaluation Score", src: "LangSmith", resource: "LangSmith", dec: 3 },
      context_evaluation: { val: sub.context_evaluation || "Unavailable", calc: sub.context_evaluation || "Unavailable", disp: sub.context_evaluation || "Unavailable", formula: "Context Evaluation Score", src: "LangSmith", resource: "LangSmith", dec: 3 },
      ground_truth_accuracy: { val: sub.ground_truth_accuracy || "Unavailable", calc: sub.ground_truth_accuracy || "Unavailable", disp: sub.ground_truth_accuracy || "Unavailable", formula: "Ground Truth Accuracy", src: "TruLens", resource: "TruLens", dec: 3 },
      trulens_faithfulness: { val: sub.trulens_faithfulness || "Unavailable", calc: sub.trulens_faithfulness || "Unavailable", disp: sub.trulens_faithfulness || "Unavailable", formula: "Faithfulness", src: "TruLens", resource: "TruLens", dec: 3 },
      hallucination_detection: { val: sub.hallucination_detection || "Unavailable", calc: sub.hallucination_detection || "Unavailable", disp: sub.hallucination_detection || "Unavailable", formula: "Hallucination Detection", src: "TruLens", resource: "TruLens", dec: 3 },
      answer_relevancy: { val: sub.answer_relevancy || "Unavailable", calc: sub.answer_relevancy || "Unavailable", disp: sub.answer_relevancy || "Unavailable", formula: "Answer Relevancy Score", src: "Confident AI", resource: "Confident AI", dec: 3 },
      faithfulness: { val: sub.faithfulness || "Unavailable", calc: sub.faithfulness || "Unavailable", disp: sub.faithfulness || "Unavailable", formula: "Faithfulness Score", src: "Confident AI", resource: "Confident AI", dec: 3 },
      hallucination: { val: sub.hallucination || "Unavailable", calc: sub.hallucination || "Unavailable", disp: sub.hallucination || "Unavailable", formula: "Hallucination Score", src: "Confident AI", resource: "Confident AI", dec: 3 },
      correctness: { val: sub.correctness || "Unavailable", calc: sub.correctness || "Unavailable", disp: sub.correctness || "Unavailable", formula: "Correctness Score", src: "Confident AI", resource: "Confident AI", dec: 3 },


      semantic_accuracy: { val: sub.semantic_accuracy || "Unavailable", calc: sub.semantic_accuracy || "Unavailable", disp: sub.semantic_accuracy || "Unavailable", formula: "Semantic Accuracy (QA)", src: "Ragas", resource: "Ragas", dec: 3 },
      faithfulness: { val: sub.faithfulness || "Unavailable", calc: sub.faithfulness || "Unavailable", disp: sub.faithfulness || "Unavailable", formula: "Faithfulness Score", src: "Ragas", resource: "Ragas", dec: 3 },
      answer_relevancy: { val: sub.answer_relevancy || "Unavailable", calc: sub.answer_relevancy || "Unavailable", disp: sub.answer_relevancy || "Unavailable", formula: "Answer Relevancy Score", src: "Ragas", resource: "Ragas", dec: 3 },
      context_precision: { val: sub.context_precision || "Unavailable", calc: sub.context_precision || "Unavailable", disp: sub.context_precision || "Unavailable", formula: "Context Precision", src: "Ragas", resource: "Ragas", dec: 3 },
      context_recall: { val: sub.context_recall || "Unavailable", calc: sub.context_recall || "Unavailable", disp: sub.context_recall || "Unavailable", formula: "Context Recall", src: "Ragas", resource: "Ragas", dec: 3 },

      runtime_execution_history: { val: sub.runtime_execution_history || "Unavailable", calc: sub.runtime_execution_history || "Unavailable", disp: sub.runtime_execution_history || "Unavailable", formula: "Execution History", src: "AgentOps", resource: "AgentOps", dec: 0 },
      agent_behaviour: { val: sub.agent_behaviour || "Unavailable", calc: sub.agent_behaviour || "Unavailable", disp: sub.agent_behaviour || "Unavailable", formula: "Agent Behaviour Score", src: "AgentOps", resource: "AgentOps", dec: 3 },
      consistency_measurement: { val: sub.consistency_measurement || "Unavailable", calc: sub.consistency_measurement || "Unavailable", disp: sub.consistency_measurement || "Unavailable", formula: "Consistency", src: "AgentOps", resource: "AgentOps", dec: 3 },
      session_metrics: { val: sub.session_metrics || "Unavailable", calc: sub.session_metrics || "Unavailable", disp: sub.session_metrics || "Unavailable", formula: "Session Metrics", src: "AgentOps", resource: "AgentOps", dec: 0 },
      stability_metrics: { val: sub.stability_metrics || "Unavailable", calc: sub.stability_metrics || "Unavailable", disp: sub.stability_metrics || "Unavailable", formula: "Stability Metrics", src: "AgentOps", resource: "AgentOps", dec: 3 },

      Quality_Score: { val: qScoreVal, calc: qScoreVal, disp: qScoreVal, formula: "0.7*Accuracy + 0.2*Consistency + 0.1*(1 - Hallucination)", src: "Quality Service (runtime telemetry)", resource: "Dynamic Calculation", dec: 4 },
    };
  }

  function renderQualityTableHtml(sub, settings, value, resourceFilter) {
    const metricsMap = calculateQualityMetrics(sub, settings, value);
    
    const fmt = (val, dec = 3) => {
      if (val === null || val === undefined || val === "Unavailable" || val === "Pending SME Review") return val;
      if (typeof val === 'number') {
        return val.toFixed(dec);
      }
      const num = parseFloat(val);
      return isNaN(num) ? val : num.toFixed(dec);
    };

    const checkMatch = (calc, disp) => {
      if (calc === "Unavailable" || disp === "Unavailable") return "Unavailable";
      if (calc === "N/A" || disp === "N/A" || calc === null || disp === null) return "MISMATCH";
      if (calc === disp) return "MATCH";
      const c = parseFloat(calc);
      const d = parseFloat(disp);
      if (isNaN(c) || isNaN(d)) {
        return calc.toString().trim() === disp.toString().trim() ? "MATCH" : "MISMATCH";
      }
      return Math.abs(c - d) < 0.001 ? "MATCH" : "MISMATCH";
    };

    const METRIC_NICE_NAMES = {
      runtime_traces: "Runtime Traces",
      llm_evaluation: "LLM Evaluation",
      hallucination_analysis: "Hallucination Rate",
      prompt_evaluation: "Prompt Evaluation",
      context_evaluation: "Context Evaluation",
      semantic_accuracy: "Semantic Accuracy",
      faithfulness: "Faithfulness",
      answer_relevancy: "Answer Relevancy",
      context_precision: "Context Precision",
      context_recall: "Context Recall",
      runtime_execution_history: "Execution History",
      agent_behaviour: "Agent Behaviour",
      consistency_measurement: "Consistency",
      session_metrics: "Session Metrics",
      stability_metrics: "Stability",
      Quality_Score: "Quality Score"
    };

    let entries = Object.entries(metricsMap);
    if (resourceFilter) {
      entries = entries.filter(([key, r]) => r.resource === resourceFilter || (r.resources && r.resources.includes(resourceFilter)));
    }
    const rowHtml = entries.map(([key, r]) => {
      const valStr = r.val !== null && r.val !== undefined ? r.val : "Unavailable";
      const calcStr = r.calc !== null && r.calc !== undefined ? r.calc : "Unavailable";
      const dispStr = r.disp !== null && r.disp !== undefined ? r.disp : "Unavailable";
      const matchStatus = checkMatch(calcStr, dispStr);
      const statusColor = matchStatus === "MATCH" ? "#4ade80" : "#ef4444";
      return `
        <tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:10px 14px;color:#94a3b8;text-align:left;font-size:12px;">${METRIC_NICE_NAMES[key] || key}</td>
          <td style="padding:10px 14px;color:#38bdf8;text-align:left;font-weight:700;font-size:12px;font-variant-numeric:tabular-nums;">${fmt(valStr, r.dec)}</td>
          <td style="padding:10px 14px;color:#e2e8f0;text-align:left;font-size:12px;">${r.formula || ''}</td>
          <td style="padding:10px 14px;color:#cbd5e1;text-align:left;font-size:12px;font-variant-numeric:tabular-nums;">${fmt(calcStr, r.dec)}</td>
          <td style="padding:10px 14px;color:#cbd5e1;text-align:left;font-size:12px;font-variant-numeric:tabular-nums;">${fmt(dispStr, r.dec)}</td>
          <td style="padding:10px 14px;color:${statusColor};text-align:left;font-weight:bold;font-size:12px;">${matchStatus}</td>
          <td style="padding:10px 14px;color:#facc15;text-align:left;font-size:12px;font-weight:600;">${r.src || ''}</td>
        </tr>
      `;
    }).join("");

    let qScoreVal = "Pending SME Review";
    let qScoreRaw = qScoreVal;
    if (metricsMap["Quality_Score"] && metricsMap["Quality_Score"].val !== undefined) {
      qScoreRaw = parseFloat(metricsMap["Quality_Score"].val);
      qScoreVal = qScoreRaw.toFixed(4);
    }
    let finalWeightedVal = "N/A";
    if (qScoreVal !== "Pending SME Review") {
      finalWeightedVal = (qScoreRaw * 20.0).toFixed(2);
    }
    
    return `
      <div style="padding:16px 20px;background:#020617;font-family:'Courier New',Courier,monospace;border-bottom:1px solid #1e293b;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
          <span style="background:#334155;color:#facc15;font-weight:800;padding:4px 10px;border-radius:6px;font-size:14px;">Q</span>
          <span style="color:#e2e8f0;font-size:13px;font-weight:700;">Quality (20%)</span>
          <span style="color:#64748b;font-size:12px;">weight: 20%</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px;">
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Raw Value</div>
            <div style="color:#38bdf8;font-size:18px;font-weight:800;">${qScoreVal}</div>
          </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Weighted (×20%)</div>
            <div style="color:#4ade80;font-size:18px;font-weight:800;">${finalWeightedVal}</div>
          </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Formula</div>
            <div style="color:#e2e8f0;font-size:11px;line-height:1.4;">Q = 0.7*Accuracy + 0.2*Consistency + 0.1*(1 - Hallucination)</div>
          </div>
        </div>
      </div>

      <div class="quality-table-wrapper" style="padding:20px;background:#090d16;font-family:'Courier New',Courier,monospace;border:1px solid #334155;border-radius:${resourceFilter ? '8px' : '0 0 8px 8px'};">
        <div style="font-size:13px;font-weight:800;color:#facc15;margin-bottom:12px;text-transform:uppercase;letter-spacing:1px;">
          ▶ ${resourceFilter ? resourceFilter.toUpperCase() + ' ' : ''}QUALITY TRACEABILITY & AUDIT
        </div>
        <table style="width:100%;border-collapse:collapse;text-align:left;">
          <thead>
            <tr style="background:#0f172a;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #334155;">
              <th style="padding:10px 14px;text-align:left;">Metric</th>
              <th style="padding:10px 14px;text-align:left;">Value</th>
              <th style="padding:10px 14px;text-align:left;">Formula</th>
              <th style="padding:10px 14px;text-align:left;">Calculated</th>
              <th style="padding:10px 14px;text-align:left;">Displayed</th>
              <th style="padding:10px 14px;text-align:left;">Status</th>
              <th style="padding:10px 14px;text-align:left;">Source</th>
            </tr>
          </thead>
          <tbody>
            ${rowHtml || `<tr><td colspan="7" style="padding:15px;color:#64748b;text-align:center;">No Quality telemetry mapped.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  }

  
  function renderGovernanceTableHtml(sub, settings, value, resourceFilter) {
    if (!sub) return `<div style="padding:15px;color:#64748b;">No Governance telemetry available.</div>`;

    const resources = sub.runtime_resources || {};
    const opa = resources["Open Policy Agent"] || {};
    const presidio = resources["Microsoft Presidio"] || {};
    const secrets = resources["Detect-Secrets"] || {};
    const keycloak = resources["Keycloak"] || {};
    const openmetadata = resources["OpenMetadata"] || {};

    // Official DPI-LS formula: G = 1 - (Total Actions / Policy Violations).
    // Both figures come exclusively from runtime telemetry.
    const totalActions = sub["Total Actions"] !== undefined ? Number(sub["Total Actions"]) : 0;
    const policyViolations = sub["Policy Violations"] !== undefined ? Number(sub["Policy Violations"]) : 0;

    // Raw Governance value from the official formula (telemetry only).
    let gScoreVal;
    if (totalActions <= 0) {
      gScoreVal = policyViolations === 0 ? 1.0 : 0.0;
    } else {
      gScoreVal = Math.max(0.0, 1.0 - (policyViolations / totalActions));
    }

    // The engine-derived value (when supplied) is authoritative for the
    // displayed Raw / Weighted numbers; fall back to the formula calc.
    if (value === undefined || value === null) value = gScoreVal;
    else gScoreVal = value;

    const finalWeightedVal = (gScoreVal * (settings?.weights?.G || 20.0)).toFixed(2);
    const metricsMap = {
      "Total Actions": { val: totalActions, calc: totalActions, disp: totalActions, formula: "Σ OPA + Presidio + Detect-Secrets + Keycloak + OpenMetadata telemetry", src: "Runtime Telemetry", resource: "Open Policy Agent / Presidio / Detect-Secrets / Keycloak / OpenMetadata", dec: 0 },
      "Policy Violations": { val: policyViolations, calc: policyViolations, disp: policyViolations, formula: "Σ Incident Frequency", src: "Runtime Telemetry", resource: "Governance Incidents", dec: 0 },
      "Governance_Score": { val: gScoreVal, calc: gScoreVal, disp: gScoreVal, formula: "1 - (Total Actions / Policy Violations)", src: "Dynamic Calculation", resource: "Calculation", dec: 4 }
    };

    if (Object.keys(opa).length > 0) {
       metricsMap["Policies Executed"] = { val: opa["Policies Executed"] || 0, calc: opa["Policies Executed"] || 0, disp: opa["Policies Executed"] || 0, formula: "OPA Rule Count", src: "Open Policy Agent", resource: "Open Policy Agent", dec: 0 };
    }
    if (Object.keys(presidio).length > 0) {
       metricsMap["PII Entities Detected"] = { val: presidio["PII Entities Detected"] || 0, calc: presidio["PII Entities Detected"] || 0, disp: presidio["PII Entities Detected"] || 0, formula: "Presidio Scans", src: "Microsoft Presidio", resource: "Microsoft Presidio", dec: 0 };
    }
    if (Object.keys(secrets).length > 0) {
       metricsMap["Secrets Found"] = { val: secrets["Secrets Found"] || 0, calc: secrets["Secrets Found"] || 0, disp: secrets["Secrets Found"] || 0, formula: "Secret Scans", src: "Detect-Secrets", resource: "Detect-Secrets", dec: 0 };
    }
    if (Object.keys(keycloak).length > 0) {
       metricsMap["Authentication Events"] = { val: keycloak["Authentication Events"] || 0, calc: keycloak["Authentication Events"] || 0, disp: keycloak["Authentication Events"] || 0, formula: "Auth Events", src: "Keycloak", resource: "Keycloak", dec: 0 };
    }
    if (Object.keys(openmetadata).length > 0) {
       metricsMap["Metadata Assets"] = { val: openmetadata["Metadata Assets"] || 0, calc: openmetadata["Metadata Assets"] || 0, disp: openmetadata["Metadata Assets"] || 0, formula: "Asset Count", src: "OpenMetadata", resource: "OpenMetadata", dec: 0 };
    }

    const fmt = (val, dec = 3) => {
      if (val === null || val === undefined) return "Unavailable";
      if (typeof val === 'number') {
        return val.toFixed(dec);
      }
      const num = parseFloat(val);
      return isNaN(num) ? val : num.toFixed(dec);
    };

    const checkMatch = (calc, disp) => {
      if (calc === "Unavailable" || disp === "Unavailable") return "Unavailable";
      if (calc === "N/A" || disp === "N/A" || calc === null || disp === null) return "MISMATCH";
      if (calc === disp) return "MATCH";
      const c = parseFloat(calc);
      const d = parseFloat(disp);
      if (isNaN(c) || isNaN(d)) {
        return calc.toString().trim() === disp.toString().trim() ? "MATCH" : "MISMATCH";
      }
      return Math.abs(c - d) < 0.001 ? "MATCH" : "MISMATCH";
    };

    let entries = Object.entries(metricsMap);
    if (resourceFilter) {
      entries = entries.filter(([key, r]) => r.resource === resourceFilter || (r.resources && r.resources.includes(resourceFilter)));
    }
    entries = entries.filter(([_, m]) => m.val !== "Unavailable");

    const rowHtml = entries.map(([key, r]) => {
      const valStr = r.val !== null && r.val !== undefined ? r.val : "Unavailable";
      const calcStr = r.calc !== null && r.calc !== undefined ? r.calc : "Unavailable";
      const dispStr = r.disp !== null && r.disp !== undefined ? r.disp : "Unavailable";
      const matchStatus = checkMatch(calcStr, dispStr);
      const statusColor = matchStatus === "MATCH" ? "#4ade80" : "#ef4444";
      return `
        <tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:10px 14px;color:#94a3b8;text-align:left;font-size:12px;">${key}</td>
          <td style="padding:10px 14px;color:#38bdf8;text-align:left;font-weight:700;font-size:12px;">${valStr}</td>
          <td style="padding:10px 14px;color:#e2e8f0;text-align:left;font-size:12px;">${r.formula || ''}</td>
          <td style="padding:10px 14px;color:#cbd5e1;text-align:left;font-size:12px;">${calcStr}</td>
          <td style="padding:10px 14px;color:#cbd5e1;text-align:left;font-size:12px;">${dispStr}</td>
          <td style="padding:10px 14px;color:${statusColor};text-align:left;font-weight:bold;font-size:12px;">${matchStatus}</td>
          <td style="padding:10px 14px;color:#facc15;text-align:left;font-size:12px;font-weight:600;">${r.src || r.resource}</td>
        </tr>
      `;
    }).join("");

    let incRows = "";
    if (sub.incidents && sub.incidents.length > 0) {
      incRows = sub.incidents
        .filter(inc => !resourceFilter || inc.source === resourceFilter)
        .map(inc => `
          <tr style="background:#1e1b4b;border-bottom:1px solid #312e81;">
            <td style="padding:10px 14px;color:#f472b6;">${escapeHtml(inc.action_name || inc.category)} &rarr; ${escapeHtml(inc.name)}</td>
            <td style="padding:10px 14px;color:#e2e8f0;">${escapeHtml(inc.source)}</td>
            <td style="padding:10px 14px;color:#cbd5e1;">${escapeHtml(inc.category)}</td>
            <td style="padding:10px 14px;color:#f87171;">Severity: ${inc.severity} (${inc.severity_weight})</td>
            <td style="padding:10px 14px;color:#fbbf24;">Freq: ${inc.frequency}</td>
            <td style="padding:10px 14px;color:#ef4444;font-weight:bold;">IMPACT</td>
            <td style="padding:10px 14px;color:#94a3b8;font-size:10px;">Trace: ${escapeHtml(inc.trace_id || 'N/A')}</td>
          </tr>
        `).join("");
    }
    const gateHtml = gScoreVal === 0.0 ? `<div style="margin-top:12px;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);padding:8px 12px;border-radius:6px;color:#fca5a5;font-size:11px;display:flex;align-items:center;gap:8px;">
      <span style="font-size:14px;">⚠️</span>
      <span>Governance Compliance Gate Fired. Score capped to 0.000 (100% Violation Rate)</span>
    </div>` : '';

    return `
      <div style="padding:16px 20px;background:#020617;font-family:'Courier New',Courier,monospace;border-bottom:1px solid #1e293b;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
          <span style="background:#334155;color:#facc15;font-weight:800;padding:4px 10px;border-radius:6px;font-size:14px;">G</span>
          <span style="color:#e2e8f0;font-size:13px;font-weight:700;">Governance (20%)</span>
          <span style="color:#64748b;font-size:12px;">weight: 20%</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px;">
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Raw Value</div>
            <div style="color:#38bdf8;font-size:18px;font-weight:800;">${gScoreVal.toFixed(4)}</div>
          </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Weighted (×20%)</div>
            <div style="color:#4ade80;font-size:18px;font-weight:800;">${finalWeightedVal}</div>
          </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Formula</div>
            <div style="color:#e2e8f0;font-size:11px;line-height:1.4;">Governance = 1 − (Policy Violations / Total Actions)</div>
          </div>
        </div>
        <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;">
          <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Governance Calculation</div>
          <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
            <div>Total Actions : ${totalActions}</div>
            <div>Policy Violations : ${policyViolations}</div>
            <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Governance Score : 1 - (${policyViolations} / ${totalActions}) = ${gScoreVal.toFixed(3)}</div>
          </div>
          ${gateHtml}
        </div>
      </div>

      <div class="governance-table-wrapper" style="padding:20px;background:#090d16;font-family:'Courier New',Courier,monospace;border:1px solid #334155;border-radius:${resourceFilter ? '8px' : '0 0 8px 8px'};">
        <div style="font-size:13px;font-weight:800;color:#facc15;margin-bottom:12px;text-transform:uppercase;letter-spacing:1px;">
          ▶ ${resourceFilter ? resourceFilter.toUpperCase() + ' ' : ''}GOVERNANCE TRACEABILITY & AUDIT
        </div>
        <table style="width:100%;border-collapse:collapse;text-align:left;">
          <thead>
            <tr style="background:#0f172a;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #334155;">
              <th style="padding:10px 14px;text-align:left;">Metric</th>
              <th style="padding:10px 14px;text-align:left;">Value</th>
              <th style="padding:10px 14px;text-align:left;">Formula</th>
              <th style="padding:10px 14px;text-align:left;">Calculated</th>
              <th style="padding:10px 14px;text-align:left;">Displayed</th>
              <th style="padding:10px 14px;text-align:left;">Status</th>
              <th style="padding:10px 14px;text-align:left;">Source</th>
            </tr>
          </thead>
          <tbody>
            ${rowHtml || `<tr><td colspan="7" style="padding:15px;color:#64748b;text-align:center;">No Governance telemetry mapped.</td></tr>`}
            ${incRows}
          </tbody>
        </table>
      </div>

      ${resourceFilter ? `
      <div style="padding:20px;background:#090d16;font-family:'Courier New',Courier,monospace;border:1px solid #334155;border-radius:8px;margin-top:12px;">
        <div style="font-size:13px;font-weight:800;color:#facc15;margin-bottom:12px;text-transform:uppercase;letter-spacing:1px;">▶ ${resourceFilter.toUpperCase()} RESOURCE CONTRIBUTION</div>
        <table style="width:100%;border-collapse:collapse;text-align:left;">
          <thead>
            <tr style="background:#0f172a;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #334155;">
              <th style="padding:10px 14px;text-align:left;">Contribution</th>
              <th style="padding:10px 14px;text-align:left;">Value</th>
            </tr>
          </thead>
          <tbody>
            <tr style="border-bottom:1px solid #1e293b;">
              <td style="padding:8px 14px;color:#38bdf8;font-weight:600;">Runtime Telemetry</td>
              <td style="padding:8px 14px;color:#e2e8f0;">${JSON.stringify(resources[resourceFilter] || {}).replace(/</g, '&lt;')}</td>
            </tr>
            <tr style="border-bottom:1px solid #1e293b;">
              <td style="padding:8px 14px;color:#38bdf8;font-weight:600;">Total Actions (telemetry sum)</td>
              <td style="padding:8px 14px;color:#e2e8f0;">${totalActions}</td>
            </tr>
            <tr style="border-bottom:1px solid #1e293b;">
              <td style="padding:8px 14px;color:#38bdf8;font-weight:600;">Policy Violations (incident freq sum)</td>
              <td style="padding:8px 14px;color:#e2e8f0;">${policyViolations}</td>
            </tr>
            <tr style="border-bottom:1px solid #1e293b;">
              <td style="padding:8px 14px;color:#38bdf8;font-weight:600;">Formula Contribution</td>
              <td style="padding:8px 14px;color:#e2e8f0;">1 − (${totalActions} / ${policyViolations})</td>
            </tr>
            <tr style="border-bottom:1px solid #1e293b;">
              <td style="padding:8px 14px;color:#38bdf8;font-weight:600;">Raw Contribution</td>
              <td style="padding:8px 14px;color:#38bdf8;font-weight:800;">${gScoreVal.toFixed(4)}</td>
            </tr>
            <tr style="border-bottom:1px solid #1e293b;">
              <td style="padding:8px 14px;color:#38bdf8;font-weight:600;">Weighted Contribution (×${settings?.weights?.G || 20.0}%)</td>
              <td style="padding:8px 14px;color:#4ade80;font-weight:800;">${finalWeightedVal}</td>
            </tr>
            <tr style="border-bottom:1px solid #1e293b;">
              <td style="padding:8px 14px;color:#38bdf8;font-weight:600;">Trace IDs</td>
              <td style="padding:8px 14px;color:#94a3b8;font-size:11px;">${(sub.incidents || []).filter(inc => !inc.source || inc.source === resourceFilter).map(inc => escapeHtml(inc.trace_id || 'N/A')).join(', ') || 'N/A'}</td>
            </tr>
            <tr style="border-bottom:1px solid #1e293b;">
              <td style="padding:8px 14px;color:#38bdf8;font-weight:600;">Policy / Incident Logs</td>
              <td style="padding:8px 14px;color:#cbd5e1;font-size:11px;">${(sub.incidents || []).filter(inc => !inc.source || inc.source === resourceFilter).map(inc => escapeHtml((inc.action_name || inc.category) + ' → ' + inc.name + ' (freq ' + inc.frequency + ')')).join('; ') || 'No incidents logged'}</td>
            </tr>
          </tbody>
        </table>
      </div>` : ''}
    `;
  }

  function renderRiskTableHtml(sub, settings, value, resourceFilter) {
    if (!sub) return `<div style="padding:15px;color:#64748b;">No Risk telemetry available.</div>`;
    
    sub = sub || {};
    settings = settings || {};
    
    const incidents = sub.incidents || [];
    const totalFreq = sub["Total Frequency"] !== undefined ? sub["Total Frequency"] : "Unavailable";
    const totalRisk = sub["Total Risk"] !== undefined ? sub["Total Risk"] : "Unavailable";
    const rmax = sub.Rmax || settings.r_max || 50;
    
    let calcRScore = 1.0;
    if (typeof totalRisk === "number") {
      calcRScore = Math.max(0, 1 - Math.min(1, totalRisk / rmax));
    }
    const rScoreVal = calcRScore;

    const metricsMap = {
      "Total Risk": { val: totalRisk, calc: totalRisk, disp: totalRisk, formula: "SUM(Freq * Severity)", src: "Runtime Metrics", resource: "Risk Engine", dec: 0 },
      "Rmax": { val: rmax, calc: rmax, disp: rmax, formula: "Max Acceptable Risk Limit", src: "Settings", resource: "System", dec: 0 },
      "Total Frequency": { val: totalFreq, calc: totalFreq, disp: totalFreq, formula: "Total Incident Freq", src: "Runtime Metrics", resource: "Risk Engine", dec: 0 },
      "Risk_Score": { val: rScoreVal, calc: calcRScore, disp: rScoreVal, formula: "1 - MIN(1, Total Risk / Rmax)", src: "Dynamic Calculation", resource: "Calculation", dec: 4 }
    };
    
    const resources = sub.runtime_resources || {};
    const llmguard = resources["LLMGuard"] || {};
    const trulens = resources["TruLens"] || {};
    const rebuff = resources["Rebuff"] || {};
    const falco = resources["Falco"] || {};
    const sentry = resources["Sentry"] || {};
    const prometheus = resources["Prometheus"] || {};

    if (Object.keys(llmguard).length > 0) {
       metricsMap["LLMGuard Prompts Blocked"] = { val: llmguard["Blocked Prompts"] || 0, calc: llmguard["Blocked Prompts"] || 0, disp: llmguard["Blocked Prompts"] || 0, formula: "LLMGuard Telemetry", src: "LLMGuard", resource: "LLMGuard", dec: 0 };
       metricsMap["LLMGuard Injection Attempts"] = { val: llmguard["Prompt Injection Attempts"] || 0, calc: llmguard["Prompt Injection Attempts"] || 0, disp: llmguard["Prompt Injection Attempts"] || 0, formula: "LLMGuard Telemetry", src: "LLMGuard", resource: "LLMGuard", dec: 0 };
    }
    if (Object.keys(trulens).length > 0) {
       metricsMap["TruLens Hallucinations"] = { val: trulens["Hallucinations"] || 0, calc: trulens["Hallucinations"] || 0, disp: trulens["Hallucinations"] || 0, formula: "TruLens Telemetry", src: "TruLens", resource: "TruLens", dec: 0 };
       metricsMap["TruLens Toxicity"] = { val: trulens["Toxicity"] || 0, calc: trulens["Toxicity"] || 0, disp: trulens["Toxicity"] || 0, formula: "TruLens Telemetry", src: "TruLens", resource: "TruLens", dec: 0 };
    }
    if (Object.keys(rebuff).length > 0) {
       metricsMap["Rebuff Attack Count"] = { val: rebuff["Attack Count"] || 0, calc: rebuff["Attack Count"] || 0, disp: rebuff["Attack Count"] || 0, formula: "Rebuff Telemetry", src: "Rebuff", resource: "Rebuff", dec: 0 };
    }
    if (Object.keys(falco).length > 0) {
       metricsMap["Falco Syscall Anomalies"] = { val: falco["Syscall Anomalies"] || 0, calc: falco["Syscall Anomalies"] || 0, disp: falco["Syscall Anomalies"] || 0, formula: "Falco Telemetry", src: "Falco", resource: "Falco", dec: 0 };
       metricsMap["Falco Container Drifts"] = { val: falco["Container Drifts"] || 0, calc: falco["Container Drifts"] || 0, disp: falco["Container Drifts"] || 0, formula: "Falco Telemetry", src: "Falco", resource: "Falco", dec: 0 };
    }
    if (Object.keys(sentry).length > 0) {
       metricsMap["Sentry Unhandled Exceptions"] = { val: sentry["Unhandled Exceptions"] || 0, calc: sentry["Unhandled Exceptions"] || 0, disp: sentry["Unhandled Exceptions"] || 0, formula: "Sentry Telemetry", src: "Sentry", resource: "Sentry", dec: 0 };
       metricsMap["Sentry Crash-Free Sessions"] = { val: sentry["Crash-Free Sessions"] || 0, calc: sentry["Crash-Free Sessions"] || 0, disp: sentry["Crash-Free Sessions"] || 0, formula: "Sentry Telemetry", src: "Sentry", resource: "Sentry", dec: 0 };
    }
    if (Object.keys(prometheus).length > 0) {
       metricsMap["Prometheus High CPU"] = { val: prometheus["High CPU"] || 0, calc: prometheus["High CPU"] || 0, disp: prometheus["High CPU"] || 0, formula: "Prometheus Telemetry", src: "Prometheus", resource: "Prometheus", dec: 0 };
       metricsMap["Prometheus Latency Spikes"] = { val: prometheus["Latency Spikes"] || 0, calc: prometheus["Latency Spikes"] || 0, disp: prometheus["Latency Spikes"] || 0, formula: "Prometheus Telemetry", src: "Prometheus", resource: "Prometheus", dec: 0 };
    }
    
    const fmt = (val, dec = 3) => {
      if (val === null || val === undefined) return "Unavailable";
      if (typeof val === 'number') {
        return val.toFixed(dec);
      }
      const num = parseFloat(val);
      return isNaN(num) ? val : num.toFixed(dec);
    };

    const checkMatch = (calc, disp) => {
      if (calc === "Unavailable" || disp === "Unavailable") return "Unavailable";
      if (calc === "N/A" || disp === "N/A" || calc === null || disp === null) return "MISMATCH";
      if (calc === disp) return "MATCH";
      const c = parseFloat(calc);
      const d = parseFloat(disp);
      if (isNaN(c) || isNaN(d)) {
        return calc.toString().trim() === disp.toString().trim() ? "MATCH" : "MISMATCH";
      }
      return Math.abs(c - d) < 0.001 ? "MATCH" : "MISMATCH";
    };

    let entries = Object.entries(metricsMap);
    if (resourceFilter) {
      entries = entries.filter(([key, r]) => r.resource === resourceFilter || (r.resources && r.resources.includes(resourceFilter)));
    }
    entries = entries.filter(([_, m]) => m.val !== "Unavailable");
    
    const req = metricsMap["Rmax"] ? metricsMap["Rmax"].val : 50;
    const valMetric = metricsMap["Total Risk"] ? metricsMap["Total Risk"].val : 0;
    
    let rScoreToUse = 1.0;
    if (metricsMap["Risk_Score"] && metricsMap["Risk_Score"].val !== undefined) {
      rScoreToUse = metricsMap["Risk_Score"].val;
    }
    if (value === undefined || value === null) value = rScoreToUse;
    
    const finalWeightedVal = (rScoreToUse * (settings?.weights?.R || 15.0)).toFixed(2);
    
    const rowHtml = entries.map(([key, r]) => {
      const valStr = r.val !== null && r.val !== undefined ? r.val : "Unavailable";
      const calcStr = r.calc !== null && r.calc !== undefined ? r.calc : "Unavailable";
      const dispStr = r.disp !== null && r.disp !== undefined ? r.disp : "Unavailable";
      const matchStatus = checkMatch(calcStr, dispStr);
      const statusColor = matchStatus === "MATCH" ? "#4ade80" : "#ef4444";
      return `
        <tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:10px 14px;color:#94a3b8;text-align:left;font-size:12px;">${key}</td>
          <td style="padding:10px 14px;color:#38bdf8;text-align:left;font-weight:700;font-size:12px;">${valStr}</td>
          <td style="padding:10px 14px;color:#e2e8f0;text-align:left;font-size:12px;">${r.formula || ''}</td>
          <td style="padding:10px 14px;color:#cbd5e1;text-align:left;font-size:12px;">${calcStr}</td>
          <td style="padding:10px 14px;color:#cbd5e1;text-align:left;font-size:12px;">${dispStr}</td>
          <td style="padding:10px 14px;color:${statusColor};text-align:left;font-weight:bold;font-size:12px;">${matchStatus}</td>
          <td style="padding:10px 14px;color:#facc15;text-align:left;font-size:12px;font-weight:600;">${r.src || r.resource}</td>
        </tr>
      `;
    }).join("");

    let incRows = "";
    if (sub.incidents && sub.incidents.length > 0) {
      incRows = sub.incidents
        .filter(inc => !resourceFilter || inc.source === resourceFilter)
        .map(inc => `
          <tr style="background:#1e1b4b;border-bottom:1px solid #312e81;">
            <td style="padding:10px 14px;color:#f472b6;">Incident: ${escapeHtml(inc.name)}</td>
            <td style="padding:10px 14px;color:#e2e8f0;">${escapeHtml(inc.source)}</td>
            <td style="padding:10px 14px;color:#cbd5e1;">${escapeHtml(inc.category)}</td>
            <td style="padding:10px 14px;color:#f87171;">Severity: ${inc.severity} (${inc.severity_weight})</td>
            <td style="padding:10px 14px;color:#fbbf24;">Freq: ${inc.frequency}</td>
            <td style="padding:10px 14px;color:#ef4444;font-weight:bold;">IMPACT</td>
            <td style="padding:10px 14px;color:#94a3b8;font-size:10px;">Trace: ${escapeHtml(inc.trace_id || 'N/A')}</td>
          </tr>
        `).join("");
    }

    return `
      <div style="padding:16px 20px;background:#020617;font-family:'Courier New',Courier,monospace;border-bottom:1px solid #1e293b;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
          <span style="background:#334155;color:#facc15;font-weight:800;padding:4px 10px;border-radius:6px;font-size:14px;">R</span>
          <span style="color:#e2e8f0;font-size:13px;font-weight:700;">Risk (15%)</span>
          <span style="color:#64748b;font-size:12px;">weight: 15%</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px;">
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Raw Value</div>
            <div style="color:#38bdf8;font-size:18px;font-weight:800;">${rScoreToUse.toFixed(4)}</div>
          </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Weighted (×15%)</div>
            <div style="color:#4ade80;font-size:18px;font-weight:800;">${finalWeightedVal}</div>
          </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Formula</div>
            <div style="color:#e2e8f0;font-size:11px;line-height:1.4;">R = 1 - min(1, SUM(freq * severity) / R_max)</div>
          </div>
        </div>
        <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;">
          <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Risk Calculation</div>
          <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
            <div>Rmax Limit : ${req}</div>
            <div>Total Risk : ${valMetric}</div>
            <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Risk Score : 1 - MIN(1, ${valMetric} / ${req}) = ${rScoreToUse.toFixed(3)}</div>
          </div>
        </div>
      </div>

      <div class="risk-table-wrapper" style="padding:20px;background:#090d16;font-family:'Courier New',Courier,monospace;border:1px solid #334155;border-radius:${resourceFilter ? '8px' : '0 0 8px 8px'};">
        <div style="font-size:13px;font-weight:800;color:#facc15;margin-bottom:12px;text-transform:uppercase;letter-spacing:1px;">
          ▶ ${resourceFilter ? resourceFilter.toUpperCase() + ' ' : ''}RISK TRACEABILITY & AUDIT
        </div>
        <table style="width:100%;border-collapse:collapse;text-align:left;">
          <thead>
            <tr style="background:#0f172a;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #334155;">
              <th style="padding:10px 14px;text-align:left;">Metric / Incident</th>
              <th style="padding:10px 14px;text-align:left;">Value / Detail 1</th>
              <th style="padding:10px 14px;text-align:left;">Formula / Detail 2</th>
              <th style="padding:10px 14px;text-align:left;">Calculated / Detail 3</th>
              <th style="padding:10px 14px;text-align:left;">Displayed / Impact</th>
              <th style="padding:10px 14px;text-align:left;">Status</th>
              <th style="padding:10px 14px;text-align:left;">Source</th>
            </tr>
          </thead>
          <tbody>
            ${rowHtml || `<tr><td colspan="7" style="padding:15px;color:#64748b;text-align:center;">No Risk telemetry mapped.</td></tr>`}
            ${incRows}
          </tbody>
        </table>
      </div>
    `;
  }

  function renderValidationTableHtml(sub, settings, value, resourceFilter) {
    const metricsMap = calculateValidationMetrics(sub, settings, value);
    
    const fmt = (val, dec = 3) => {
      if (val === null || val === undefined) return "Unavailable";
      if (typeof val === 'number') {
        return val.toFixed(dec);
      }
      const num = parseFloat(val);
      return isNaN(num) ? val : num.toFixed(dec);
    };

    const checkMatch = (calc, disp) => {
      if (calc === "Unavailable" || disp === "Unavailable") return "Unavailable";
      if (calc === "N/A" || disp === "N/A" || calc === null || disp === null) return "MISMATCH";
      if (calc === disp) return "MATCH";
      const c = parseFloat(calc);
      const d = parseFloat(disp);
      if (isNaN(c) || isNaN(d)) {
        return calc.toString().trim() === disp.toString().trim() ? "MATCH" : "MISMATCH";
      }
      return Math.abs(c - d) < 0.001 ? "MATCH" : "MISMATCH";
    };

    const METRIC_NICE_NAMES = {
      answer_relevancy: "Answer Relevancy",
      faithfulness: "Faithfulness",
      hallucination: "Hallucination",
      correctness: "Correctness",
      evaluation_status: "Evaluation Status",
      evaluation_count: "Evaluation Count",
      run_id: "Run ID",
      experiment_id: "Experiment ID",
      runtime_traces: "Runtime Traces",
      validation_latency: "Validation Latency",
      success_count: "Success Count",
      failure_count: "Failure Count",
      error_rate: "Error Rate",
      active_validation_requests: "Active Requests",
      dependency_health: "Dependency Health"
    };

    let entries = Object.entries(metricsMap);
    if (resourceFilter) {
      entries = entries.filter(([key, r]) => r.resource === resourceFilter || (r.resources && r.resources.includes(resourceFilter)));
    }
    // Filter out rows where value is "Unavailable"
    entries = entries.filter(([_, m]) => m.val !== "Unavailable");


    const req = metricsMap["Required_Components"] ? metricsMap["Required_Components"].val : 0;
    const val = metricsMap["Validated_Components"] ? metricsMap["Validated_Components"].val : 0;
    
    let vScoreVal = 1.0;
    if (metricsMap["Validation_Score"] && metricsMap["Validation_Score"].val !== undefined) {
      vScoreVal = metricsMap["Validation_Score"].val;
    }
    const finalWeightedVal = (vScoreVal * 10.0).toFixed(2);
    
    let gateHtml = "";
    if (vScoreVal < 0.60) {
      gateHtml = `
        <div style="margin-top:10px;background:#ef444420;border:1px solid #ef4444;border-radius:6px;padding:10px;color:#f87171;font-size:11px;">
          <strong style="color:#ef4444;">Validation Gate Triggered</strong><br/>
          Unsafe = TRUE
        </div>
      `;
    }

    const breakdownObj = sub.Breakdown || {};
    const breakdownHtml = Object.keys(breakdownObj).length > 0 ? `
      <div style="margin-top:4px;margin-bottom:4px;padding-left:10px;border-left:2px solid #334155;">
        <div style="color:#94a3b8;font-size:10px;text-transform:uppercase;margin-bottom:2px;">Breakdown</div>
        ${Object.entries(breakdownObj).map(([res, counts]) => 
          `<div style="display:flex;justify-content:space-between;width:150px;">
            <span>${res}</span><span>${counts.val} / ${counts.req}</span>
          </div>`
        ).join('')}
      </div>
    ` : "";

    const rowHtml = entries.map(([key, r]) => {
      const valStr = r.val !== null && r.val !== undefined ? r.val : "Unavailable";
      const calcStr = r.calc !== null && r.calc !== undefined ? r.calc : "Unavailable";
      const dispStr = r.disp !== null && r.disp !== undefined ? r.disp : "Unavailable";
      const matchStatus = checkMatch(calcStr, dispStr);
      const statusColor = matchStatus === "MATCH" ? "#4ade80" : "#ef4444";
      return `
        <tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:10px 14px;color:#94a3b8;text-align:left;font-size:12px;">${METRIC_NICE_NAMES[key] || key}</td>
          <td style="padding:10px 14px;color:#38bdf8;text-align:left;font-weight:700;font-size:12px;">${valStr}</td>
          <td style="padding:10px 14px;color:#e2e8f0;text-align:left;font-size:12px;">${r.formula || ''}</td>
          <td style="padding:10px 14px;color:#cbd5e1;text-align:left;font-size:12px;">${calcStr}</td>
          <td style="padding:10px 14px;color:#cbd5e1;text-align:left;font-size:12px;">${dispStr}</td>
          <td style="padding:10px 14px;color:${statusColor};text-align:left;font-weight:bold;font-size:12px;">${matchStatus}</td>
          <td style="padding:10px 14px;color:#facc15;text-align:left;font-size:12px;font-weight:600;">${r.src || r.resource}</td>
        </tr>
      `;
    }).join("");

    return `
      ${resourceFilter ? '' : `
      <div style="padding:16px 20px;background:#020617;font-family:'Courier New',Courier,monospace;border-bottom:1px solid #1e293b;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
          <span style="background:#334155;color:#facc15;font-weight:800;padding:4px 10px;border-radius:6px;font-size:14px;">V</span>
          <span style="color:#e2e8f0;font-size:13px;font-weight:700;">Validation (10%)</span>
          <span style="color:#64748b;font-size:12px;">weight: 10%</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px;">
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Raw Value</div>
            <div style="color:#38bdf8;font-size:18px;font-weight:800;">${vScoreVal.toFixed(4)}</div>
          </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Weighted (×10%)</div>
            <div style="color:#4ade80;font-size:18px;font-weight:800;">${finalWeightedVal}</div>
          </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Formula</div>
            <div style="color:#e2e8f0;font-size:11px;line-height:1.4;">Validation Score = Validated Components / Required Components</div>
          </div>
        </div>
        <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;">
          <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Validation Calculation</div>
          <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
            <div>Required Components : ${req}</div>
            ${breakdownHtml}
            <div>Validated Components : ${val}</div>
            <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Validation Score : ${val} / ${req} = ${vScoreVal.toFixed(3)}</div>
          </div>
          ${gateHtml}
        </div>
      </div>
      `}

      <div class="validation-table-wrapper" style="padding:20px;background:#090d16;font-family:'Courier New',Courier,monospace;border:1px solid #334155;border-radius:${resourceFilter ? '8px' : '0 0 8px 8px'};">
        <div style="font-size:13px;font-weight:800;color:#facc15;margin-bottom:12px;text-transform:uppercase;letter-spacing:1px;">
          ▶ ${resourceFilter ? resourceFilter.toUpperCase() + ' ' : ''}VALIDATION TRACEABILITY & AUDIT
        </div>
        <table style="width:100%;border-collapse:collapse;text-align:left;">
          <thead>
            <tr style="background:#0f172a;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #334155;">
              <th style="padding:10px 14px;text-align:left;">Metric</th>
              <th style="padding:10px 14px;text-align:left;">Value</th>
              <th style="padding:10px 14px;text-align:left;">Formula</th>
              <th style="padding:10px 14px;text-align:left;">Calculated</th>
              <th style="padding:10px 14px;text-align:left;">Displayed</th>
              <th style="padding:10px 14px;text-align:left;">Status</th>
              <th style="padding:10px 14px;text-align:left;">Source</th>
            </tr>
          </thead>
          <tbody>
            ${rowHtml}
          </tbody>
        </table>
      </div>
    `;
  }

  function renderCostTableHtml(sub, settings, value, resourceFilter) {
    const metricsMap = calculateCostMetrics(sub, settings, value);
    
    const fmt = (val, dec = 6) => {
      if (val === null || val === undefined) return "Unavailable";
      if (typeof val === 'number') {
        return val.toFixed(dec);
      }
      const num = parseFloat(val);
      return isNaN(num) ? val : num.toFixed(dec);
    };

    const tolerance = 0.00001;
    const checkMatch = (calc, disp) => {
      if (calc === "Unavailable" || disp === "Unavailable") return "Unavailable";
      if (calc === "N/A" || disp === "N/A" || calc === null || disp === null) return "MISMATCH";
      let cleanCalc = calc.toString().replace(/[$%]/g, '');
      let cleanDisp = disp.toString().replace(/[$%]/g, '');
      const c = parseFloat(cleanCalc);
      const d = parseFloat(cleanDisp);
      if (isNaN(c) || isNaN(d)) {
        return calc.toString().trim() === disp.toString().trim() ? "MATCH" : "MISMATCH";
      }
      return Math.abs(c - d) < tolerance ? "MATCH" : "MISMATCH";
    };

    const METRIC_NICE_NAMES = {
      input_tokens: "Input Tokens",
      output_tokens: "Output Tokens",
      prompt_cost: "Prompt Cost",
      completion_cost: "Completion Cost",
      model_cost: "Model Cost",
      ai_cost_per_output: "AI Cost Per Output",
      human_cost_per_output: "Human Cost Per Output",
      utilization: "Utilization",
      efficiency_ratio: "Efficiency Ratio",
      cost_score: "Cost Score",
      tco: "TCO",
      // OpenLIT
      "Input Tokens": "Input Tokens",
      "Output Tokens": "Output Tokens",
      "Total Tokens": "Total Tokens",
      "Prompt Cost": "Prompt Cost",
      "Completion Cost": "Completion Cost",
      "Total LLM Cost": "Total LLM Cost",
      "Request Count": "Request Count",
      "Model Name": "Model Name",
      "Provider": "Provider",
      "Latency": "Latency",
      "Time To First Token": "Time To First Token",
      "Error Count": "Error Count",
      // OpenCost
      "CPU Cost": "CPU Cost",
      "Memory Cost": "Memory Cost",
      "GPU Cost": "GPU Cost",
      "Storage Cost": "Storage Cost",
      "Network Cost": "Network Cost",
      "Idle Cost": "Idle Cost",
      "Total Infrastructure Cost": "Total Infrastructure Cost",
      "Cluster Cost": "Cluster Cost"
    };

    let entries = Object.entries(metricsMap);
    if (resourceFilter) {
      entries = entries.filter(([key, r]) => r.resource === resourceFilter || (r.resources && r.resources.includes(resourceFilter)));
    }
    entries = entries.filter(([_, m]) => m.val !== "Unavailable");
    const rowHtml = entries.map(([key, r]) => {
      const isDollarMetric = ['prompt_cost', 'completion_cost', 'model_cost', 'ai_cost_per_output', 'human_cost_per_output', 'tco'].includes(key);
      // Also detect dollar-prefixed values from OpenLIT/OpenCost (e.g. "$1.20")
      const hasDollarValue = typeof r.val === 'string' && r.val.startsWith('$');
      const prefix = (isDollarMetric && !hasDollarValue) ? "$" : "";
      
      const calcStr = r.calc !== null && r.calc !== undefined ? prefix + fmt(r.calc, r.dec).replace("Unavailable", "") : "Unavailable";
      const dispStr = r.disp !== null && r.disp !== undefined ? prefix + fmt(r.disp, r.dec).replace("Unavailable", "") : "Unavailable";
      const valStr = r.val !== null && r.val !== undefined 
        ? prefix + (r.dec === 0 && typeof r.val === 'number' ? r.val.toFixed(0) : fmt(r.val, r.dec)).replace("Unavailable", "")
        : "Unavailable";
      
      // Fix prefix prepending to Unavailable
      const finalCalcStr = r.calc !== null && r.calc !== undefined ? calcStr : "Unavailable";
      const finalDispStr = r.disp !== null && r.disp !== undefined ? dispStr : "Unavailable";
      const finalValStr = r.val !== null && r.val !== undefined ? valStr : "Unavailable";
      const rawCalcStr = fmt(r.calc, r.dec);
      const rawDispStr = fmt(r.disp, r.dec);
      const matchStatus = checkMatch(rawCalcStr, rawDispStr);
      const statusColor = matchStatus === "MATCH" ? "#4ade80" : "#ef4444";
      return `
        <tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:10px 14px;color:#94a3b8;text-align:left;font-size:12px;">${METRIC_NICE_NAMES[key] || key}</td>
          <td style="padding:10px 14px;color:#38bdf8;text-align:left;font-weight:700;font-size:12px;font-variant-numeric:tabular-nums;">${finalValStr}</td>
          <td style="padding:10px 14px;color:#e2e8f0;text-align:left;font-size:12px;">${r.formula}</td>
          <td style="padding:10px 14px;color:#cbd5e1;text-align:left;font-size:12px;font-variant-numeric:tabular-nums;">${finalCalcStr}</td>
          <td style="padding:10px 14px;color:#cbd5e1;text-align:left;font-size:12px;font-variant-numeric:tabular-nums;">${finalDispStr}</td>
          <td style="padding:10px 14px;color:${statusColor};text-align:left;font-weight:bold;font-size:12px;">${matchStatus}</td>
          <td style="padding:10px 14px;color:#facc15;text-align:left;font-size:12px;font-weight:600;">${r.src}</td>
        </tr>
      `;
    }).join("");

    // Retrieve final values for the formula widget
    // Value represents the raw Cost metric (0.0 to 1.0)
    const costScoreVal = (value !== undefined && value !== null) ? value : 1.0;
    const finalWeightedVal = (costScoreVal * 5.0).toFixed(2);
    
    return `
      <div style="padding:16px 20px;background:#020617;font-family:'Courier New',Courier,monospace;border-bottom:1px solid #1e293b;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
          <span style="background:#334155;color:#facc15;font-weight:800;padding:4px 10px;border-radius:6px;font-size:14px;">C</span>
          <span style="color:#e2e8f0;font-size:13px;font-weight:700;">Cost (5%)</span>
          <span style="color:#64748b;font-size:12px;">weight: 5%</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px;">
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Raw Value</div>
            <div style="color:#38bdf8;font-size:18px;font-weight:800;">${costScoreVal.toFixed(4)}</div>
          </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Weighted (×5%)</div>
            <div style="color:#4ade80;font-size:18px;font-weight:800;">${finalWeightedVal}</div>
          </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Formula</div>
            <div style="color:#e2e8f0;font-size:11px;line-height:1.4;">C = min(1, AI Cost per Output / Human Cost per Output) × Utilization Factor</div>
          </div>
        </div>
      </div>

      <div class="cost-table-wrapper" style="padding:20px;background:#090d16;font-family:'Courier New',Courier,monospace;border:1px solid #334155;border-radius:${resourceFilter ? '8px' : '0 0 8px 8px'};">
        <div style="font-size:13px;font-weight:800;color:#facc15;margin-bottom:12px;text-transform:uppercase;letter-spacing:1px;">
          ▶ ${resourceFilter ? resourceFilter.toUpperCase() + ' ' : ''}COST TRACEABILITY & EFFICIENCY
        </div>
        <table style="width:100%;border-collapse:collapse;text-align:left;">
          <thead>
            <tr style="background:#0f172a;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #334155;">
              <th style="padding:10px 14px;text-align:left;">Metric</th>
              <th style="padding:10px 14px;text-align:left;">Value</th>
              <th style="padding:10px 14px;text-align:left;">Formula</th>
              <th style="padding:10px 14px;text-align:left;">Calculated</th>
              <th style="padding:10px 14px;text-align:left;">Displayed</th>
              <th style="padding:10px 14px;text-align:left;">Status</th>
              <th style="padding:10px 14px;text-align:left;">Source</th>
            </tr>
          </thead>
          <tbody>
            ${rowHtml}
          </tbody>
        </table>
      </div>
    `;
  }

  function calculateProductivityMetrics(sub, settings, value) {
    sub = sub || {};
    settings = settings || {};
    
    let pScoreVal = 1.0;
    if (value !== undefined && value !== null) {
      pScoreVal = value;
    }

    return {
      worker_concurrency: { val: sub.worker_concurrency, calc: sub.worker_concurrency, disp: sub.worker_concurrency, formula: "Raw Value", src: "Prometheus", resource: "Prometheus", dec: 0 },
      decision_branches: { val: sub.decision_branches, calc: (sub.decision_branches || 0) * 5.0, disp: (sub.decision_branches || 0) * 5.0, formula: "val × 5.0", src: "OpenTelemetry", resource: "OpenTelemetry", dec: 2 },
      api_calls: { val: sub.api_calls, calc: (sub.api_calls || 0) * 2.5, disp: (sub.api_calls || 0) * 2.5, formula: "val × 2.5", src: "Langfuse", resource: "Langfuse", dec: 2 },
      execution_duration: { val: sub.execution_duration, calc: sub.execution_duration, disp: sub.execution_duration, formula: "Raw Value", src: "Langfuse", resource: "Langfuse", dec: 2 },
      token_depth: { val: sub.token_depth, calc: (sub.token_depth || 0) * 0.001, disp: (sub.token_depth || 0) * 0.001, formula: "val × 0.001", src: "Apache SkyWalking", resource: "Apache SkyWalking", dec: 3 },
      throughput: { val: sub.throughput, calc: sub.throughput, disp: sub.throughput, formula: "Raw Value", src: "Langfuse", resource: "Langfuse", dec: 2 },
      cpu_usage: { val: sub.cpu_usage, calc: sub.cpu_usage, disp: sub.cpu_usage, formula: "Raw Value", src: "Prometheus", resource: "Prometheus", dec: 2 },
      memory_usage: { val: sub.memory_usage, calc: sub.memory_usage, disp: sub.memory_usage, formula: "Raw Value", src: "Prometheus", resource: "Prometheus", dec: 2 },
      infrastructure_health: { val: sub.infrastructure_health, calc: sub.infrastructure_health, disp: sub.infrastructure_health, formula: "Raw Value", src: "Prometheus", resource: "Prometheus", dec: 0 },
      success_rate: { val: sub.success_rate, calc: sub.success_rate, disp: sub.success_rate, formula: "Raw Value", src: "Langfuse", resource: "Langfuse", dec: 2 },
      failure_rate: { val: sub.failure_rate, calc: sub.failure_rate, disp: sub.failure_rate, formula: "Raw Value", src: "Langfuse", resource: "Langfuse", dec: 2 },
      resolution_velocity: { val: sub.resolution_velocity, calc: sub.resolution_velocity, disp: sub.resolution_velocity, formula: "Raw Value", src: "Langfuse", resource: "Langfuse", dec: 2 },
      assigned_tasks: { val: sub.assigned, calc: sub.assigned, disp: sub.assigned, formula: "Raw Value", src: "Workflow Layer", resource: "Workflow Layer", dec: 0 },
      completed_tasks: { val: sub.completed, calc: sub.completed, disp: sub.completed, formula: "Raw Value", src: "Workflow Layer", resource: "Workflow Layer", dec: 0 },
      failed_tasks: { val: sub.failed, calc: sub.failed, disp: sub.failed, formula: "Raw Value", src: "Workflow Layer", resource: "Workflow Layer", dec: 0 },
      human_baseline: { val: sub.human_baseline, calc: sub.human_baseline, disp: sub.human_baseline, formula: "Raw Value", src: "Settings Layer", resource: "Settings Layer", dec: 3 },
      human_complexity: { val: sub['E[C_Human]'], calc: sub['E[C_Human]'], disp: sub['E[C_Human]'], formula: "Raw Value", src: "Prometheus", resource: "Prometheus", dec: 3 },
      normalization_factor: { val: sub.normalization_factor, calc: sub.normalization_factor, disp: sub.normalization_factor, formula: "γ = E[C_AI] / E[C_Human]", src: "Backend Engine", resource: "Backend Engine", dec: 3 },
      effective_output: { val: sub.effective_output, calc: sub.effective_output, disp: sub.effective_output, formula: "Completed Tasks × γ", src: "Backend Engine", resource: "Backend Engine", dec: 3 },
      Productivity_Score: { val: pScoreVal, calc: pScoreVal, disp: pScoreVal, formula: "min(1, Effective Output / Baseline)", src: "Productivity Service", resource: "Backend Engine", dec: 4 },
      AI_Complexity: { val: sub['E[C_AI]'], calc: sub['E[C_AI]'], disp: sub['E[C_AI]'], formula: "Raw Value", src: "Backend Engine", resource: "Backend Engine", dec: 3 }
    };
  }

  function renderProductivityTableHtml(sub, settings, value, resourceFilter) {
    const metricsMap = calculateProductivityMetrics(sub, settings, value);
    
    const fmt = (val, dec = 3) => {
      if (val === null || val === undefined || val === "Unavailable") return val;
      if (typeof val === 'number') return val.toFixed(dec);
      const num = parseFloat(val);
      return isNaN(num) ? val : num.toFixed(dec);
    };

    const checkMatch = (calc, disp) => {
      if (calc === "Unavailable" || disp === "Unavailable") return "Unavailable";
      if (calc === "N/A" || disp === "N/A" || calc === null || disp === null) return "MISMATCH";
      if (calc === disp) return "MATCH";
      const c = parseFloat(calc);
      const d = parseFloat(disp);
      if (isNaN(c) || isNaN(d)) {
        return calc.toString().trim() === disp.toString().trim() ? "MATCH" : "MISMATCH";
      }
      return Math.abs(c - d) < 0.001 ? "MATCH" : "MISMATCH";
    };

    const METRIC_NICE_NAMES = {
      worker_concurrency: "Worker Concurrency",
      decision_branches: "Decision Branches",
      api_calls: "API Calls",
      execution_duration: "Execution Duration",
      token_depth: "Token Depth",
      throughput: "Throughput",
      cpu_usage: "CPU Usage",
      memory_usage: "Memory Usage",
      infrastructure_health: "Infrastructure Health",
      success_rate: "Success Rate",
      failure_rate: "Failure Rate",
      resolution_velocity: "Resolution Velocity",
      assigned_tasks: "Assigned Tasks",
      completed_tasks: "Completed Tasks",
      failed_tasks: "Failed Tasks",
      human_baseline: "Human Baseline",
      human_complexity: "Human Complexity",
      normalization_factor: "Normalization Factor (γ)",
      effective_output: "Effective Output",
      Productivity_Score: "Productivity Score",
      AI_Complexity: "AI Complexity"
    };

    let entries = Object.entries(metricsMap);
    if (resourceFilter) {
      entries = entries.filter(([key, r]) => r.resource === resourceFilter || (r.resources && r.resources.includes(resourceFilter)));
    }
    const rowHtml = entries.map(([key, r]) => {
      const valStr = r.val !== null && r.val !== undefined ? r.val : "Unavailable";
      const calcStr = r.calc !== null && r.calc !== undefined ? r.calc : "Unavailable";
      const dispStr = r.disp !== null && r.disp !== undefined ? r.disp : "Unavailable";
      const matchStatus = checkMatch(calcStr, dispStr);
      const statusColor = matchStatus === "MATCH" ? "#4ade80" : "#ef4444";
      return `
        <tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:10px 14px;color:#94a3b8;text-align:left;font-size:12px;">${METRIC_NICE_NAMES[key] || key}</td>
          <td style="padding:10px 14px;color:#38bdf8;text-align:left;font-weight:700;font-size:12px;font-variant-numeric:tabular-nums;">${fmt(valStr, r.dec)}</td>
          <td style="padding:10px 14px;color:#e2e8f0;text-align:left;font-size:12px;">${r.formula || ''}</td>
          <td style="padding:10px 14px;color:#cbd5e1;text-align:left;font-size:12px;font-variant-numeric:tabular-nums;">${fmt(calcStr, r.dec)}</td>
          <td style="padding:10px 14px;color:#cbd5e1;text-align:left;font-size:12px;font-variant-numeric:tabular-nums;">${fmt(dispStr, r.dec)}</td>
          <td style="padding:10px 14px;color:${statusColor};text-align:left;font-weight:bold;font-size:12px;">${matchStatus}</td>
          <td style="padding:10px 14px;color:#facc15;text-align:left;font-size:12px;font-weight:600;">${r.src || ''}</td>
        </tr>
      `;
    }).join("");

    let pScoreVal = (value !== undefined && value !== null) ? value : 1.0;
    const finalWeightedVal = (pScoreVal * 15.0).toFixed(2);
    
    return `
      <div style="padding:16px 20px;background:#020617;font-family:'Courier New',Courier,monospace;border-bottom:1px solid #1e293b;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
          <span style="background:#334155;color:#facc15;font-weight:800;padding:4px 10px;border-radius:6px;font-size:14px;">P</span>
          <span style="color:#e2e8f0;font-size:13px;font-weight:700;">Productivity (15%)</span>
          <span style="color:#64748b;font-size:12px;">weight: 15%</span>
        </div>
        
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:10px;">
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">AI Output (Completed)</div>
            <div style="color:#38bdf8;font-size:18px;font-weight:800;">${fmt(metricsMap.completed_tasks.val, 0)}</div>
          </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Normalization (γ)</div>
            <div style="color:#facc15;font-size:18px;font-weight:800;">${fmt(metricsMap.normalization_factor.val, 3)}</div>
          </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Human Baseline</div>
            <div style="color:#38bdf8;font-size:18px;font-weight:800;">${fmt(metricsMap.human_baseline.val, 1)}</div>
          </div>
        </div>

        <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:12px;">
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Productivity Score</div>
            <div style="color:#38bdf8;font-size:18px;font-weight:800;">${pScoreVal.toFixed(4)}</div>
          </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Weighted (×15%)</div>
            <div style="color:#4ade80;font-size:18px;font-weight:800;">${finalWeightedVal}</div>
          </div>
        </div>

        <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;margin-bottom:12px;">
          <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Formula</div>
          <div style="color:#e2e8f0;font-size:11px;line-height:1.4;">P = min(1.0, (AI Output × γ) / Human Baseline)</div>
        </div>
      </div>

      <div class="productivity-table-wrapper" style="padding:20px;background:#090d16;font-family:'Courier New',Courier,monospace;border:1px solid #334155;border-radius:${resourceFilter ? '8px' : '0 0 8px 8px'};">
        <div style="font-size:13px;font-weight:800;color:#facc15;margin-bottom:12px;text-transform:uppercase;letter-spacing:1px;">
          ▶ ${resourceFilter ? resourceFilter.toUpperCase() + ' ' : ''}PRODUCTIVITY TRACEABILITY & AUDIT
        </div>
        <table style="width:100%;border-collapse:collapse;text-align:left;">
          <thead>
            <tr style="background:#0f172a;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #334155;">
              <th style="padding:10px 14px;text-align:left;">Metric</th>
              <th style="padding:10px 14px;text-align:left;">Value</th>
              <th style="padding:10px 14px;text-align:left;">Formula</th>
              <th style="padding:10px 14px;text-align:left;">Calculated</th>
              <th style="padding:10px 14px;text-align:left;">Displayed</th>
              <th style="padding:10px 14px;text-align:left;">Status</th>
              <th style="padding:10px 14px;text-align:left;">Source</th>
            </tr>
          </thead>
          <tbody>
            ${rowHtml || `<tr><td colspan="7" style="padding:15px;color:#64748b;text-align:center;">No Productivity telemetry mapped.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  }

  /**
   * Renders the inline drilldown panel for the Airport Board.
   * Called when the user clicks a metric column (P/Q/E/G/R/V/C) on a row.
   */
  
  function calculateExecutionMetrics(sub, settings, value) {
    sub = sub || {};
    settings = settings || {};
    
    let attempts = 0;
    if (!isNaN(Number(sub.iterations_used))) attempts = Number(sub.iterations_used);
    else if (!isNaN(Number(sub.attempts))) attempts = Number(sub.attempts);
    else if (!isNaN(Number(sub.total_attempts))) attempts = Number(sub.total_attempts);

    let successful = 0;
    if (!isNaN(Number(sub.successful))) successful = Number(sub.successful);
    else if (!isNaN(Number(sub.successful_executions))) successful = Number(sub.successful_executions);
    else if (sub.execution_status === 'success' || sub.execution_success === 1 || sub.execution_success === '1' || sub.execution_success === 'true') successful = attempts; // Fallback to attempts if status is success and no raw count is provided
    
    let calcEScore = 0;
    if (attempts > 0) calcEScore = successful / attempts;
    
    // Remove the display override that masks mathematical inconsistencies
    const eScoreVal = calcEScore;

    return {
      trace_captured:     { val: sub.trace_captured    || "Unavailable", calc: sub.trace_captured    || "Unavailable", disp: sub.trace_captured    || "Unavailable", formula: "Langfuse Trace Payload",               src: "Langfuse (runtime telemetry)",   resource: "Langfuse",   dec: 0 },
      trace_id:           { val: sub.trace_id          || "Unavailable", calc: sub.trace_id          || "Unavailable", disp: sub.trace_id          || "Unavailable", formula: "Langfuse Trace ID",                    src: "Langfuse (runtime telemetry)",   resource: "Langfuse",   dec: 0 },
      trace_status:       { val: sub.trace_status      || "Unavailable", calc: sub.trace_status      || "Unavailable", disp: sub.trace_status      || "Unavailable", formula: "Langfuse Trace Status",                src: "Langfuse (runtime telemetry)",   resource: "Langfuse",   dec: 0 },
      Total_Attempts:     { val: attempts, calc: attempts, disp: attempts, formula: "Agent execution iterations",     src: "Phoenix (runtime telemetry)",   resource: "Phoenix",   dec: 0 },
      Successful_Attempts:{ val: successful, calc: successful, disp: successful, formula: "Successful agent executions", src: "Phoenix (runtime telemetry)", resource: "Phoenix", dec: 0 },
      execution_status:   { val: sub.execution_status  || "Unavailable", calc: sub.execution_status  || "Unavailable", disp: sub.execution_status  || "Unavailable", formula: "Phoenix Execution Status",             src: "Phoenix (runtime telemetry)",   resource: "Phoenix",   dec: 0 },
      Execution_Score:    { val: eScoreVal, calc: calcEScore, disp: eScoreVal,   formula: "Successful / Total Attempts",     src: "Phoenix (runtime telemetry)",   resource: "Phoenix",   dec: 4 },
      workflow_execution: { val: sub.workflow_execution || "Unavailable", calc: sub.workflow_execution || "Unavailable", disp: sub.workflow_execution || "Unavailable", formula: "Workflow execution payload",          src: "Traceloop (runtime telemetry)", resource: "Traceloop", dec: 0 },
      workflow_status:    { val: sub.workflow_status   || "Unavailable", calc: sub.workflow_status   || "Unavailable", disp: sub.workflow_status   || "Unavailable", formula: "Workflow execution status",            src: "Traceloop (runtime telemetry)", resource: "Traceloop", dec: 0 },
      root_span:          { val: sub.root_span         || "Unavailable", calc: sub.root_span         || "Unavailable", disp: sub.root_span         || "Unavailable", formula: "Workflow root span",                   src: "Traceloop (runtime telemetry)", resource: "Traceloop", dec: 0 },
      otel_span_count:    { val: sub.otel_span_count   || "Unavailable", calc: sub.otel_span_count   || "Unavailable", disp: sub.otel_span_count   || "Unavailable", formula: "OpenTelemetry Span Count",             src: "OpenTelemetry (runtime telemetry)", resource: "OpenTelemetry", dec: 0 },
      otel_status:        { val: sub.otel_status       || "Unavailable", calc: sub.otel_status       || "Unavailable", disp: sub.otel_status       || "Unavailable", formula: "OpenTelemetry Export Status",          src: "OpenTelemetry (runtime telemetry)", resource: "OpenTelemetry", dec: 0 },
      jaeger_trace:       { val: sub.jaeger_trace      || "Unavailable", calc: sub.jaeger_trace      || "Unavailable", disp: sub.jaeger_trace      || "Unavailable", formula: "Jaeger Trace ID",                      src: "Jaeger (runtime telemetry)", resource: "Jaeger", dec: 0 },
    };
  }

  function renderExecutionTableHtml(sub, settings, value, resourceFilter) {
    const metricsMap = calculateExecutionMetrics(sub, settings, value);
    
    const fmt = (val, dec = 3) => {
      if (val === null || val === undefined) return "Unavailable";
      if (typeof val === 'number') {
        return val.toFixed(dec);
      }
      const num = parseFloat(val);
      return isNaN(num) ? val : num.toFixed(dec);
    };

    const checkMatch = (calc, disp) => {
      if (calc === "Unavailable" || disp === "Unavailable") return "Unavailable";
      if (calc === "N/A" || disp === "N/A" || calc === null || disp === null) return "MISMATCH";
      if (calc === disp) return "MATCH";
      const c = parseFloat(calc);
      const d = parseFloat(disp);
      if (isNaN(c) || isNaN(d)) {
        return calc.toString().trim() === disp.toString().trim() ? "MATCH" : "MISMATCH";
      }
      return Math.abs(c - d) < 0.001 ? "MATCH" : "MISMATCH";
    };

    const METRIC_NICE_NAMES = {
      trace_captured: "Trace Captured",
      trace_id: "Trace ID",
      trace_status: "Trace Status",
      workflow_execution: "Workflow Execution",
      workflow_status: "Workflow Status",
      root_span: "Root Span",
      iterations_used: "Iterations Used",
      Total_Attempts: "Total Attempts",
      Successful_Attempts: "Successful Attempts",
      execution_status: "Execution Status",
      Execution_Score: "Execution Score",
      otel_span_count: "OTel Span Count",
      otel_status: "OTel Status",
      jaeger_trace: "Jaeger Trace ID"
    };

    let entries = Object.entries(metricsMap);
    if (resourceFilter) {
      entries = entries.filter(([key, r]) => r.resource === resourceFilter || (r.resources && r.resources.includes(resourceFilter)));
    }
    entries = entries.filter(([_, m]) => m.val !== "Unavailable");

    const attempts = metricsMap["Total_Attempts"] ? metricsMap["Total_Attempts"].val : 0;
    const successful = metricsMap["Successful_Attempts"] ? metricsMap["Successful_Attempts"].val : 0;
    
    let eScoreVal = 0.0;
    if (metricsMap["Execution_Score"] && metricsMap["Execution_Score"].val !== undefined) {
      eScoreVal = metricsMap["Execution_Score"].val;
    }
    const finalWeightedVal = (eScoreVal * 15.0).toFixed(2);
    
    const rowHtml = entries.map(([key, r]) => {
      const valStr = r.val !== null && r.val !== undefined ? r.val : "Unavailable";
      const calcStr = r.calc !== null && r.calc !== undefined ? r.calc : "Unavailable";
      const dispStr = r.disp !== null && r.disp !== undefined ? r.disp : "Unavailable";
      const matchStatus = checkMatch(calcStr, dispStr);
      const statusColor = matchStatus === "MATCH" ? "#4ade80" : "#ef4444";
      return `
        <tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:10px 14px;color:#94a3b8;text-align:left;font-size:12px;">${METRIC_NICE_NAMES[key] || key}</td>
          <td style="padding:10px 14px;color:#38bdf8;text-align:left;font-weight:700;font-size:12px;">${valStr}</td>
          <td style="padding:10px 14px;color:#e2e8f0;text-align:left;font-size:12px;">${r.formula || ''}</td>
          <td style="padding:10px 14px;color:#cbd5e1;text-align:left;font-size:12px;">${calcStr}</td>
          <td style="padding:10px 14px;color:#cbd5e1;text-align:left;font-size:12px;">${dispStr}</td>
          <td style="padding:10px 14px;color:${statusColor};text-align:left;font-weight:bold;font-size:12px;">${matchStatus}</td>
          <td style="padding:10px 14px;color:#facc15;text-align:left;font-size:12px;font-weight:600;">${r.src || r.resource}</td>
        </tr>
      `;
    }).join("");

    return `
      <div style="padding:16px 20px;background:#020617;font-family:'Courier New',Courier,monospace;border-bottom:1px solid #1e293b;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
          <span style="background:#334155;color:#facc15;font-weight:800;padding:4px 10px;border-radius:6px;font-size:14px;">E</span>
          <span style="color:#e2e8f0;font-size:13px;font-weight:700;">Execution (15%)</span>
          <span style="color:#64748b;font-size:12px;">weight: 15%</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px;">
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Raw Value</div>
            <div style="color:#38bdf8;font-size:18px;font-weight:800;">${eScoreVal.toFixed(4)}</div>
          </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Weighted (×15%)</div>
            <div style="color:#4ade80;font-size:18px;font-weight:800;">${finalWeightedVal}</div>
          </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Formula</div>
            <div style="color:#e2e8f0;font-size:11px;line-height:1.4;">Execution Score = Successful / Total Attempts</div>
          </div>
        </div>
        <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px;">
          <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Execution Calculation</div>
          <div style="display:flex;flex-direction:column;gap:4px;color:#e2e8f0;font-size:12px;">
            <div>Total Attempts : ${attempts}</div>
            <div>Successful Attempts : ${successful}</div>
            <div style="margin-top:4px;font-weight:bold;color:#38bdf8;">Execution Score : ${successful} / ${attempts} = ${eScoreVal.toFixed(3)}</div>
          </div>
        </div>
      </div>

      <div class="execution-table-wrapper" style="padding:20px;background:#090d16;font-family:'Courier New',Courier,monospace;border:1px solid #334155;border-radius:${resourceFilter ? '8px' : '0 0 8px 8px'};">
        <div style="font-size:13px;font-weight:800;color:#facc15;margin-bottom:12px;text-transform:uppercase;letter-spacing:1px;">
          ▶ ${resourceFilter ? resourceFilter.toUpperCase() + ' ' : ''}EXECUTION TRACEABILITY & AUDIT
        </div>
        <table style="width:100%;border-collapse:collapse;text-align:left;">
          <thead>
            <tr style="background:#0f172a;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #334155;">
              <th style="padding:10px 14px;text-align:left;">Metric</th>
              <th style="padding:10px 14px;text-align:left;">Value</th>
              <th style="padding:10px 14px;text-align:left;">Formula</th>
              <th style="padding:10px 14px;text-align:left;">Calculated</th>
              <th style="padding:10px 14px;text-align:left;">Displayed</th>
              <th style="padding:10px 14px;text-align:left;">Status</th>
              <th style="padding:10px 14px;text-align:left;">Source</th>
            </tr>
          </thead>
          <tbody>
            ${rowHtml || `<tr><td colspan="7" style="padding:15px;color:#64748b;text-align:center;">No Execution telemetry mapped.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  }

  function metricDetailHtml(key, value, sub, rating) {
    if (key === "C") return renderCostTableHtml(sub, null, value);
    if (key === "V") return renderValidationTableHtml(sub, null, value);
    if (key === "G") return renderGovernanceTableHtml(sub, null, value);
    if (key === "R") return renderRiskTableHtml(sub, null, value);
    if (key === "Q") return renderQualityTableHtml(sub, null, value);
    if (key === "E") return renderExecutionTableHtml(sub, null, value);
    if (key === "P") return renderProductivityTableHtml(sub, null, value);

    const label  = METRIC_LABELS[key]  || key;
    const w_m = rating && rating.weighted_metrics ? rating.weighted_metrics : {};
    const w_u = rating && rating.weights_used ? rating.weights_used : {};
    const weight = w_u[key] !== undefined ? (w_u[key] * 100).toFixed(1) : "—";

    const contrib = w_m[key] !== undefined && w_m[key] !== null 
      ? parseFloat(w_m[key]).toFixed(2) 
      : "—";
    const valueStr = (typeof value === 'number') ? parseFloat(value.toFixed(4)) : "—";

    // Sub-metric rows
    let subRows = "";
    if (sub && typeof sub === 'object') {
      subRows = Object.entries(sub)
        .filter(([k]) => k !== 'violations' && k !== 'details')
        .map(([k, v]) => {
          let disp = v;
          if (typeof v === 'number') disp = parseFloat(v.toFixed(6));
          if (Array.isArray(v))      disp = v.length + " items";
          if (typeof v === 'boolean') disp = v ? "true" : "false";
          return `<tr>
            <td style="padding:5px 10px;color:#94a3b8;border-bottom:1px solid #1e293b;font-size:12px;">${escapeHtml(String(k))}</td>
            <td style="padding:5px 10px;color:#e2e8f0;border-bottom:1px solid #1e293b;font-size:12px;font-weight:600;">${escapeHtml(String(disp))}</td>
          </tr>`;
        }).join("");
    }
    const subTable = subRows
      ? `<table style="width:100%;border-collapse:collapse;margin-top:10px;">${subRows}</table>`
      : `<div style="color:#475569;font-size:12px;margin-top:8px;">No sub-metric data available.</div>`;

    return `
      <div style="padding:16px 20px;background:#020617;font-family:'Courier New',Courier,monospace;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
          <span style="background:#334155;color:#facc15;font-weight:800;padding:4px 10px;border-radius:6px;font-size:14px;">${escapeHtml(key)}</span>
          <span style="color:#e2e8f0;font-size:13px;font-weight:700;">${escapeHtml(label)}</span>
          <span style="color:#64748b;font-size:12px;">weight: ${weight}%</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:12px;">
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Raw Value</div>
            <div style="color:#38bdf8;font-size:18px;font-weight:800;">${valueStr}</div>
          </div>
          <div style="background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:10px;">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Weighted (×${weight}%)</div>
            <div style="color:#4ade80;font-size:18px;font-weight:800;">${contrib}</div>
          </div>
        </div>
        <div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Sub-metrics</div>
        ${subTable}
      </div>`;
  }

  function metricLineHtml(key, value, sub, isExpanded, rating) {
    const labelStr = METRIC_LABELS[key] || key;
    
    const w_m = rating && rating.weighted_metrics ? rating.weighted_metrics : {};
    const w_u = rating && rating.weights_used ? rating.weights_used : {};
    
    const weightVal = w_u[key];
    const weightStr = weightVal !== undefined ? ` (${(weightVal * 100).toFixed(1)}%)` : "";
    const label = `${labelStr}${weightStr}`;
    const formula = "—"; // formulas removed from frontend
    let subHtml = "";

    if (sub && Object.keys(sub).length > 0) {
      const parts = Object.entries(sub).map(([k, v]) => {
         if (k === 'violations' || k === 'details') return "";
         let disp = v;
         if (typeof v === 'number') disp = parseFloat(v.toFixed(6));
         if (Array.isArray(v)) disp = v.length + ' items';
         return `<div>${escapeHtml(k)}: <strong>${escapeHtml(disp)}</strong></div>`;
      }).join("");
      const displayStyle = isExpanded ? 'block' : 'none';
      let formulaDisplay = "";
      if (typeof value === 'number') {
        const valueStr = parseFloat(value.toFixed(4));
        if (weightVal !== undefined) {
          const contrib = w_m[key];
          const contribStr = contrib !== undefined && contrib !== null
            ? (Number.isInteger(contrib) ? contrib.toString() : contrib.toFixed(2))
            : "—";
          formulaDisplay =
            `Value = ${valueStr}<br>` +
            `<span style="color:#475569">weighted contribution: ` +
            `<strong>${contribStr}</strong></span>`;
        } else {
          formulaDisplay = `Value = ${valueStr}`;
        }
      }

      // Governance panel — surface the actual violation list so an
      // operator can see *which* rules fired. Group by rule name and
      // show a count + the most recent timestamp for each rule. This
      // is the only place the dashboard tells you the qualitative
      // reason behind a low G; without it the score alone doesn't
      // tell you whether to look at PII, secrets, authz, or audit.
      let violationsHtml = "";
      if (key === "G") {
        const totalActions = sub["Total Actions"] !== undefined ? Number(sub["Total Actions"]) : 0;
        const policyViolations = sub["Policy Violations"] !== undefined ? Number(sub["Policy Violations"]) : 0;
        const gIncidents = Array.isArray(sub.incidents) ? sub.incidents : [];

        const rateStr = policyViolations <= 0
          ? `No policy violations recorded &mdash; G = 1.0`
          : `G = 1 &minus; (${totalActions} / ${policyViolations}) = ${parseFloat((1 - totalActions / policyViolations).toFixed(4))}`;

        const rows = gIncidents
          .map((inc, i) => `
            <div style="display:flex;flex-direction:column;gap:2px;padding:4px 0;border-bottom:1px solid #f1f5f9;">
              <span style="color:#64748b;font-weight:600;">Incident ${i + 1} &mdash; ${escapeHtml(inc.action_name || inc.category)} &rarr; ${escapeHtml(inc.name)} <span style="font-weight:normal;color:#94a3b8">(${escapeHtml(inc.source)})</span> <span style="float:right">freq ${inc.frequency}</span></span>
            </div>`)
          .join("");

        violationsHtml = `<div style="margin-top:8px;padding-top:6px;border-top:1px dashed #e2e8f0">
          <div style="font-weight:600;color:#991b1b;margin-bottom:4px">${rateStr}</div>
          <div style="font-size:10px;line-height:1.4">${rows || '<span style="color:#64748b">No governance incidents recorded.</span>'}</div>
        </div>`;
      }

      let executionsHtml = "";
      if (key === "E" && Array.isArray(sub.details) && sub.details.length) {
        const detailsList = sub.details.map((d, i) => {
          let nameStr = typeof d === 'string' ? d : d.name;
          let statusHtml = "";
          if (typeof d === 'object') {
            statusHtml = d.ok 
              ? '<span style="color:#10b981;float:right;font-size:10px;font-weight:600">✓ success</span>' 
              : '<span style="color:#ef4444;float:right;font-size:10px;font-weight:600">✗ failed</span>';
          }
          return `<div style="padding:2px 0;border-bottom:1px solid #f1f5f9"><span style="color:#64748b;margin-right:6px">#${i+1}</span><code style="background:#f1f5f9;color:#334155;padding:1px 4px;border-radius:3px;font-size:10px">${escapeHtml(nameStr)}</code>${statusHtml}</div>`;
        }).join("");
        executionsHtml = `<div style="margin-top:8px;padding-top:6px;border-top:1px dashed #e2e8f0">
          <div style="font-weight:600;color:#334155;margin-bottom:4px">Attempt Details</div>
          <div style="font-size:10px;line-height:1.4;max-height:120px;overflow-y:auto;padding-right:4px">${detailsList}</div>
        </div>`;
      }

      subHtml = `<div class="metric-detail" style="display:${displayStyle}; grid-column: 1 / -1; padding: 10px; background: #f8fafc; border-radius: 8px; margin-top: 6px; font-size: 11px; color: var(--muted); cursor: text;">
        <div style="font-family: monospace; margin-bottom: 8px; color: #334155; padding-bottom: 6px; border-bottom: 1px solid #e2e8f0;">${formulaDisplay}</div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px;">${parts}</div>
        ${violationsHtml}
        ${executionsHtml}
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
        <span class="metric-value">${METRIC_WEIGHTS[key] ? fmtWeightedMetric(value, METRIC_WEIGHTS[key]) : fmtMetric(value)}</span>
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

  function agentCardHtml(rating, expandedSet = new Set(), enterpriseData = {}) {
    const metrics = ["P", "Q", "E", "G", "R", "V", "C"]
      .map((k) => metricLineHtml(k, rating.metrics ? rating.metrics[k] : null, rating.sub_metrics ? rating.sub_metrics[k] : null, expandedSet.has(k), rating))
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

    // The composite is the weighted arithmetic mean of the 7
    // metrics × 100 — `raw_score` on the API. When no gate fires,
    // ``score == raw_score``. When a gate fires, ``score`` is
    // force-pinned to 69 (top of "Needs Optimization") and the
    // raw_score is preserved separately so the user can verify the
    // math. Surface the raw_score as a small subtitle under the
    // score so the discrepancy is explicit.
    const rawScore = Number.isFinite(rating.raw_score) ? rating.raw_score : null;
    
    // Enterprise Action Links
    const agentId = rating.agent_id || 'agent-001';
    const onb = enterpriseData.onboarding;
    const mgr = enterpriseData.managerRatings || [];
    const cust = enterpriseData.customerRatings || [];
    
    let entInfo = "";
    if (onb && onb.manager) {
      entInfo += `<span><strong>Manager:</strong> ${escapeHtml(onb.manager)}</span><br>`;
    }
    if (mgr.length) {
      entInfo += `<span><strong>Latest Mgr Rating:</strong> ${mgr[0].rating}/5</span><br>`;
    }
    if (cust.length) {
      entInfo += `<span><strong>Latest Cust Rating:</strong> ${cust[0].rating}/5</span><br>`;
    }

    const enterpriseBanner = `
      <div style="margin-top:20px; padding-top:16px; border-top:1px solid var(--border);">
        <h4 style="font-size:12px;text-transform:uppercase;color:var(--muted);margin-bottom:8px;">Enterprise Worker Management</h4>
        <div style="font-size:12px;color:var(--text);margin-bottom:12px;line-height:1.4;">
          ${entInfo}
        </div>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <a href="/widget/onboarding.html?agent=${agentId}" target="_blank" style="background:var(--surface2);color:var(--accent);padding:4px 8px;border-radius:4px;font-size:11px;text-decoration:none;">Onboarding</a>
          <a href="/widget/agent-config.html?agent=${agentId}" target="_blank" style="background:var(--surface2);color:var(--accent);padding:4px 8px;border-radius:4px;font-size:11px;text-decoration:none;">Configuration</a>
          <a href="/widget/manager-review.html?agent=${agentId}" target="_blank" style="background:var(--surface2);color:var(--accent);padding:4px 8px;border-radius:4px;font-size:11px;text-decoration:none;">Manager Review</a>
          <a href="/widget/customer-feedback.html?agent=${agentId}" target="_blank" style="background:var(--surface2);color:var(--accent);padding:4px 8px;border-radius:4px;font-size:11px;text-decoration:none;">Customer Feedback</a>
        </div>
      </div>
    `;

    return `
      <div class="card" part="card">
        <div class="head">
          <div>
            <div class="score">${fmtScore(rawScore !== null ? rawScore : rating.score)}</div>
          </div>
          <div style="display:flex;flex-direction:column;gap:6px;align-items:flex-end">
            ${bandPill(bandForScore(rawScore !== null ? rawScore : rating.score, rating.band))}
            ${coverageBadge(rating)}
          </div>
        </div>
        ${unsafeBanner}
        ${capNote}
        <div class="metrics">${metrics}</div>
        ${missing}
        ${enterpriseBanner}
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
      const td = ev.target.closest("td.metric-cell");
      const tr = ev.target.closest("tr.agent-row");

      if (td && tr) {
        // — Metric column click: open/close inline detail row —
        const agentId = tr.dataset.agentId;
        const key = td.dataset.key;
        
        // Only one Cost (C) detail row should be open at any time.
        const existingCost = this.shadowRoot.querySelector("tr.cost-detail-row");
        const existingDetail = this.shadowRoot.querySelector("tr.detail-row");

        if (key === "C") {
          // If we click C, collapse any general detail row first
          if (existingDetail) {
            existingDetail.remove();
            this._expandedKey = null;
            this._expandedAgentId = null;
          }

          if (existingCost) {
            const isSelf = (tr.nextElementSibling === existingCost);
            existingCost.remove();
            this._expandedKey = null;
            this._expandedAgentId = null;
            if (isSelf) {
              // Clicked same C cell on same row: collapsed now, return
              ev.preventDefault();
              return;
            }
          }

          const row = (this._data || []).find(r => r.agent_id === agentId);
          if (!row) return;
          const m = row.metrics || {};
          const sub = row.sub_metrics || {};
          const detailHtml = metricDetailHtml(key, m[key], sub[key], this._settings || {});
          const detailTr = document.createElement("tr");
          detailTr.className = "cost-detail-row";
          detailTr.dataset.expandedKey = key;
          detailTr.innerHTML = `<td colspan="9" style="padding:0;border:1px solid #334155;background:#020617;">${detailHtml}</td>`;
          tr.parentNode.insertBefore(detailTr, tr.nextSibling);
          
          this._expandedAgentId = agentId;
          this._expandedKey = key;
          
          ev.preventDefault();
          return;
        } else {
          // For other keys
          if (existingCost) {
            existingCost.remove();
            this._expandedKey = null;
            this._expandedAgentId = null;
          }

          const existing = tr.nextElementSibling;
          if (existing && existing.classList.contains("detail-row")) {
            if (existing.dataset.expandedKey === key) {
              existing.remove(); // toggle off same column
              this._expandedKey = null;
              this._expandedAgentId = null;
              ev.preventDefault();
              return;
            }
            existing.remove(); // replace with different column
          } else if (existingDetail) {
            existingDetail.remove(); // remove other agent's detail row
          }

          const row = (this._data || []).find(r => r.agent_id === agentId);
          if (!row) return;
          const m = row.metrics || {};
          const sub = row.sub_metrics || {};
          const detailHtml = metricDetailHtml(key, m[key], sub[key], this.rating);
          const detailTr = document.createElement("tr");
          detailTr.className = "detail-row";
          detailTr.dataset.expandedKey = key;
          detailTr.innerHTML = `<td colspan="9" style="padding:0;border:1px solid #334155;background:#020617;">${detailHtml}</td>`;
          tr.parentNode.insertBefore(detailTr, tr.nextSibling);
          
          this._expandedAgentId = agentId;
          this._expandedKey = key;
          
          ev.preventDefault();
          return;
        }
      }

      if (tr) {
        // — Row click (not on metric cell): select the agent —
        this._select(tr.dataset.agentId, tr.dataset.agentName || tr.dataset.agentId);
        ev.preventDefault();
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
        const [rRatings, rSettings] = await Promise.all([
          fetch(`${apiBase(this)}/ratings`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/settings`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
        ]);
        if (!rRatings.ok) throw new Error(`HTTP ${rRatings.status}`);
        const data = await rRatings.json();
        if (rSettings.ok) {
          this._settings = await rSettings.json();
        }
        this._render({ data });
      } catch (e) {
        this._render({ error: e && e.message ? e.message : String(e) });
      }
    }
    _render({ loading, data, error }) {
      if (data) {
        this._data = data;
      } else {
        this._data = [];
      }
      
      if (loading) {
        this._renderShell(`<div class="empty">Loading…</div>`);
        return;
      }
      if (error) {
        this._renderShell(`<div class="err">Cannot load board: ${escapeHtml(error)}</div>`);
        return;
      }
      if (!data || data.length === 0) {
        this._renderShell(`<div class="empty">No agents scored yet.</div>`);
        return;
      }

      const table = this.shadowRoot.querySelector("table");
      if (table) {
        let allUpdated = true;
        for (const item of data) {
          const tr = this.shadowRoot.querySelector(`tr.agent-row[data-agent-id="${cssEscape(item.agent_id)}"]`);
          if (!tr) {
            allUpdated = false;
            break;
          }
        }
        
        if (allUpdated) {
          for (const item of data) {
            const tr = this.shadowRoot.querySelector(`tr.agent-row[data-agent-id="${cssEscape(item.agent_id)}"]`);
            const scoreToUse = (item.raw_score !== undefined && item.raw_score !== null) ? item.raw_score : item.score;
            
            const wm = item.weighted_metrics || {};
            const m  = item.metrics || {};
            const KEYS = ["P", "Q", "E", "G", "R", "V", "C"];
            
            let sum = 0;
            KEYS.forEach(k => {
              if (wm[k] !== null && wm[k] !== undefined) sum += (wm[k] * 100);
            });
            
            tr.cells[1].textContent = sum.toFixed(1);
            tr.cells[2].textContent = fmtScore(scoreToUse);
            tr.cells[2].style.color = getScoreColor(scoreToUse);

            KEYS.forEach((k, idx) => {
              const td = tr.cells[idx + 3];
              if (td) {
                const val = wm[k] !== undefined ? wm[k] : m[k];
                const display = (val !== null && val !== undefined)
                  ? (wm[k] !== undefined ? (val * 100).toFixed(2) : val.toFixed(2))
                  : "\u2014";
                td.textContent = display;
              }
            });
            
            if (this._expandedAgentId === item.agent_id && this._expandedKey) {
              const detailTr = tr.nextElementSibling;
              const expectedClass = (this._expandedKey === "C") ? "cost-detail-row" : "detail-row";
              if (detailTr && detailTr.classList.contains(expectedClass) && detailTr.dataset.expandedKey === this._expandedKey) {
                const detailM = item.metrics || {};
                const detailSub = item.sub_metrics || {};
                const detailHtml = metricDetailHtml(this._expandedKey, detailM[this._expandedKey], detailSub[this._expandedKey], item);
                const td = detailTr.querySelector("td");
                if (td) {
                  td.innerHTML = detailHtml;
                }
              } else {
                if (detailTr && (detailTr.classList.contains("detail-row") || detailTr.classList.contains("cost-detail-row"))) {
                  detailTr.remove();
                }
                const detailM = item.metrics || {};
                const detailSub = item.sub_metrics || {};
                const detailHtml = metricDetailHtml(this._expandedKey, detailM[this._expandedKey], detailSub[this._expandedKey], item);
                const newDetailTr = document.createElement("tr");
                newDetailTr.className = expectedClass;
                newDetailTr.dataset.expandedKey = this._expandedKey;
                newDetailTr.innerHTML = `<td colspan="9" style="padding:0;border:1px solid #334155;background:#020617;">${detailHtml}</td>`;
                tr.parentNode.insertBefore(newDetailTr, tr.nextSibling);
              }
            } else {
              const detailTr = tr.nextElementSibling;
              if (detailTr && (detailTr.classList.contains("detail-row") || detailTr.classList.contains("cost-detail-row"))) {
                detailTr.remove();
              }
            }
          }
          return;
        }
      }

      const body = `
      <div style="background:#020617;border-radius:10px;border:2px solid #334155;overflow:hidden;font-family:'Courier New',Courier,monospace;">
        <div style="background:linear-gradient(135deg,#1e293b,#0f172a);padding:14px 24px;text-align:center;border-bottom:2px solid #334155;">
          <span style="color:#facc15;font-size:16px;font-weight:800;letter-spacing:3px;text-transform:uppercase;">AGENT DEPARTURES</span>
        </div>
        <table style="width:100%;border-collapse:collapse;">
          <thead>
            <tr style="background:#0f172a;color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:1px;">
              <th style="padding:10px 14px;border:1px solid #1e293b;text-align:left;">AGENT</th>
              <th style="padding:10px;border:1px solid #1e293b;text-align:center;color:#facc15;">PI</th>
              <th style="padding:10px;border:1px solid #1e293b;text-align:center;color:#38bdf8;">DPI-LS</th>
              <th style="padding:10px;border:1px solid #1e293b;text-align:center;cursor:pointer;" title="Productivity (15%)">P</th>
              <th style="padding:10px;border:1px solid #1e293b;text-align:center;cursor:pointer;" title="Quality (20%)">Q</th>
              <th style="padding:10px;border:1px solid #1e293b;text-align:center;cursor:pointer;" title="Execution (15%)">E</th>
              <th style="padding:10px;border:1px solid #1e293b;text-align:center;cursor:pointer;" title="Governance (20%)">G</th>
              <th style="padding:10px;border:1px solid #1e293b;text-align:center;cursor:pointer;" title="Risk (15%)">R</th>
              <th style="padding:10px;border:1px solid #1e293b;text-align:center;cursor:pointer;" title="Validation (10%)">V</th>
              <th style="padding:10px;border:1px solid #1e293b;text-align:center;cursor:pointer;" title="Cost (5%)">C</th>
            </tr>
          </thead>
          <tbody>
            ${data.map(boardRowHtml).join("")}
          </tbody>
        </table>
      </div>`;
      this._renderShell(body);
      
      // Restore expanded detail row if one was open
      if (this._expandedAgentId && this._expandedKey) {
        const tr = this.shadowRoot.querySelector(`tr.agent-row[data-agent-id="${cssEscape(this._expandedAgentId)}"]`);
        if (tr) {
          const row = (this._data || []).find(r => r.agent_id === this._expandedAgentId);
          if (row) {
            const m = row.metrics || {};
            const sub = row.sub_metrics || {};
            const detailHtml = metricDetailHtml(this._expandedKey, m[this._expandedKey], sub[this._expandedKey], row);
            const detailTr = document.createElement("tr");
            detailTr.className = (this._expandedKey === "C") ? "cost-detail-row" : "detail-row";
            detailTr.dataset.expandedKey = this._expandedKey;
            detailTr.innerHTML = `<td colspan="10" style="padding:0;border:1px solid #334155;background:#020617;">${detailHtml}</td>`;
            tr.parentNode.insertBefore(detailTr, tr.nextSibling);
          }
        }
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
        const pScore = fetch(`${apiBase(this)}/agents/${encodeURIComponent(id)}/score`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } });
        const pOnboard = fetch(`${apiBase(this)}/agents/${encodeURIComponent(id)}/onboard`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } });
        const pManager = fetch(`${apiBase(this)}/agents/${encodeURIComponent(id)}/manager-rating`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } });
        const pCustomer = fetch(`${apiBase(this)}/agents/${encodeURIComponent(id)}/customer-rating`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } });
        
        const [rScore, rOnboard, rManager, rCustomer] = await Promise.all([pScore, pOnboard, pManager, pCustomer]);

        if (rScore.status === 404) {
          this._render({ notFound: true, id });
          return;
        }
        if (!rScore.ok) throw new Error(`HTTP ${rScore.status}`);
        
        const rating = await rScore.json();
        const onboarding = rOnboard.ok ? await rOnboard.json() : null;
        const managerRatings = rManager.ok ? await rManager.json() : [];
        const customerRatings = rCustomer.ok ? await rCustomer.json() : [];
        
        this._render({ rating, onboarding, managerRatings, customerRatings, id });
      } catch (e) {
        this._render({ error: e && e.message ? e.message : String(e) });
      }
    }
    _render({ loading, notFound, rating, onboarding, managerRatings, customerRatings, error, id }) {
      let body;
      if (loading) body = `<div class="empty">Loading…</div>`;
      else if (error) body = `<div class="err">${escapeHtml(error)}</div>`;
      else if (notFound) body = `<div class="empty">No score yet for <code>${escapeHtml(id)}</code>.</div>`;
      else {
        body = agentCardHtml(rating, this._expandedMetrics, {onboarding, managerRatings, customerRatings});
      }
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
        headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Content-Type": "application/json", ...(opts && opts.headers) },
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
        const r = await fetch(`${apiBase(this)}/settings`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token") } });
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
          headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Content-Type": "application/json" },
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

  class DpiLsCostEvaluation extends Pollable {
    static get observedAttributes() {
      return ["api-base", "poll-interval"];
    }
    connectedCallback() {
      super.connectedCallback();
      this._results = [];
      this.shadowRoot.addEventListener("click", async (ev) => {
        const target = ev.target;
        if (target.dataset.action === "run-eval") {
          this._runEvaluations();
        } else if (target.classList.contains("verify-btn")) {
          const res = target.dataset.resource;
          const met = target.dataset.metric;
          this._verifyDashboard(res, met);
        }
      });
    }
    async _tick() {
      try {
        const [resCost, resVal, resQual, resProd, resExec, resRisk, resGov, urlsCost, urlsVal, urlsQual, urlsProd, urlsExec, urlsRisk, urlsGov] = await Promise.all([
          fetch(`${apiBase(this)}/api/cost-evaluation/results`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/validation-evaluation/results`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/quality-evaluation/results`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/productivity-evaluation/results`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/execution-evaluation/results`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/risk-evaluation/results`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/governance-evaluation/results`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/cost-evaluation/urls`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/validation-evaluation/urls`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/quality-evaluation/urls`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/productivity-evaluation/urls`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/execution-evaluation/urls`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/risk-evaluation/urls`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/governance-evaluation/urls`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } })
        ]);

        const [rC, rV, rQ, rP, rE, rR, rG, uC, uV, uQ, uP, uE, uR, uG] = await Promise.all([
          resCost.json(), resVal.json(), resQual.json(), resProd.json(), resExec.json(), resRisk.json(), resGov.json(),
          urlsCost.json(), urlsVal.json(), urlsQual.json(), urlsProd.json(), urlsExec.json(), urlsRisk.json(), urlsGov.json()
        ]);
        
        this._results = [...rC, ...rV, ...rQ, ...rP, ...rE, ...rR, ...rG];
        this._urls = { ...uC, ...uV, ...uQ, ...uP, ...uE, ...uR, ...uG };
        this._render({});
      } catch (e) {
        this._render({ error: e.message });
      }
    }
    async _runEvaluations() {
      try {
        this._render({ loading: true });
        const [evalCost, evalVal, evalQual, evalProd, evalExec, evalRisk, evalGov, urlsCost, urlsVal, urlsQual, urlsProd, urlsExec, urlsRisk, urlsGov] = await Promise.all([
          fetch(`${apiBase(this)}/api/cost-evaluation/evaluate`, { method: "POST", headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/validation-evaluation/evaluate`, { method: "POST", headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/quality-evaluation/evaluate`, { method: "POST", headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/productivity-evaluation/evaluate`, { method: "POST", headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/execution-evaluation/evaluate`, { method: "POST", headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/risk-evaluation/evaluate`, { method: "POST", headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/governance-evaluation/evaluate`, { method: "POST", headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/cost-evaluation/urls`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/validation-evaluation/urls`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/quality-evaluation/urls`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/productivity-evaluation/urls`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/execution-evaluation/urls`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/risk-evaluation/urls`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } }),
          fetch(`${apiBase(this)}/api/governance-evaluation/urls`, { headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Accept": "application/json" } })
        ]);

        const [rC, rV, rQ, rP, rE, rR, rG, uC, uV, uQ, uP, uE, uR, uG] = await Promise.all([
          evalCost.json(), evalVal.json(), evalQual.json(), evalProd.json(), evalExec.json(), evalRisk.json(), evalGov.json(),
          urlsCost.json(), urlsVal.json(), urlsQual.json(), urlsProd.json(), urlsExec.json(), urlsRisk.json(), urlsGov.json()
        ]);
        
        this._results = [...rC, ...rV, ...rQ, ...rP, ...rE, ...rR, ...rG];
        this._urls = { ...uC, ...uV, ...uQ, ...uP, ...uE, ...uR, ...uG };
        this._render({});
      } catch (e) {
        this._render({ error: e.message });
      }
    }
        async _verifyDashboard(resource, metric) {
      try {
        function getCat(m) {
          const PROD_M = ["Langfuse", "Prometheus", "Grafana Tempo", "Apache SkyWalking"];
          const COST_M = ["Grafana", "OpenLIT", "OpenCost"];
          const VAL_M  = ["DeepEval", "Jaeger", "Zipkin", "Guardrails AI", "Pydantic AI", "Instructor"];
          const QUAL_M = ["Phoenix", "Traceloop", "LangSmith", "Ragas", "AgentOps", "Confident AI", "TruLens"];
          if (PROD_M.includes(m)) return "productivity-evaluation";
          if (COST_M.includes(m)) return "cost-evaluation";
          if (VAL_M.includes(m))  return "validation-evaluation";
          return "quality-evaluation";
        }
        let endpoint = getCat(resource);
        if (["Rebuff", "LLMGuard", "TruLens", "Falco", "Sentry", "Prometheus"].includes(resource)) { endpoint = "risk-evaluation"; }
        else if (["Detect-Secrets", "Microsoft Presidio", "Open Policy Agent", "Keycloak", "OpenMetadata"].includes(resource)) { endpoint = "governance-evaluation"; }
        
        const r = await fetch(`${apiBase(this)}/api/${endpoint}/verify-dashboard`, {
          method: "POST",
          headers: { "Authorization": "Bearer " + localStorage.getItem("token"), "Content-Type": "application/json" },
          body: JSON.stringify({ resource_name: resource, metric: metric })
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        this._tick();
      } catch (e) {
        alert("Verification failed: " + e.message);
      }
    }
    _render({ loading, error }) {
      if (loading) {
        this._renderShell(`<div class="empty">Evaluating and running checks…</div>`);
        return;
      }
      if (error) {
        this._renderShell(`<div class="err">${escapeHtml(error)}</div>`);
        return;
      }
      if (!this._results || this._results.length === 0) {
        this._renderShell(`
          <div class="empty">
            No evaluations run yet. 
            <button data-action="run-eval" style="margin-top:10px">Run Initial Technical Evaluation</button>
          </div>
        `);
        return;
      }

      // Resource dashboard URLs from API
      const RESOURCE_URLS = this._urls || {};

      // Nice display names for each metric key
      const METRIC_NICE = {
        model_cost: 'Model Cost', token_cost: 'Token Cost',
        prompt_cost: 'Prompt Cost', completion_cost: 'Completion Cost',
        AI_cost_per_output: 'AI Cost / Output', Human_cost_per_output: 'Human Cost / Output',
        utilization: 'Utilization', total_cost_of_ownership: 'Total Cost (TCO)',
        validated_components: 'Validated Components', required_components: 'Required Components',
        validation_score: 'Validation Score',
        hallucination_score: 'Hallucination Score', relevance_score: 'Relevance Score',
        consistency: 'Consistency', user_feedback_score: 'User Feedback Score',
        model_correctness: 'Model Correctness',
        // OpenLIT
        'Total LLM Cost': 'Total LLM Cost', 'Request Count': 'Request Count',
        'Total Tokens': 'Total Tokens', 'Input Tokens': 'Input Tokens',
        'Output Tokens': 'Output Tokens', 'Prompt Cost': 'Prompt Cost',
        'Completion Cost': 'Completion Cost', 'Latency': 'Latency',
        'Time To First Token': 'Time To First Token', 'Error Count': 'Error Count',
        'Model Name': 'Model Name', 'Provider': 'Provider',
        // OpenCost
        'CPU Cost': 'CPU Cost', 'Memory Cost': 'Memory Cost',
        'GPU Cost': 'GPU Cost', 'Storage Cost': 'Storage Cost',
        'Network Cost': 'Network Cost', 'Idle Cost': 'Idle Cost',
        'Total Infrastructure Cost': 'Total Infrastructure Cost',
        'Cluster Cost': 'Cluster Cost',
      };
      const COST_M     = ['model_cost','token_cost','prompt_cost','completion_cost','AI_cost_per_output','Human_cost_per_output','utilization','total_cost_of_ownership'];
      const VALID_M    = ['validated_components','required_components','validation_score'];
      const QUALITY_M  = ['hallucination_score','relevance_score','groundedness_score','user_feedback_score','model_correctness'];
      const PROD_M     = ['worker_concurrency', 'execution_duration', 'throughput', 'resolution_velocity', 'human_complexity', 'decision_branches', 'api_calls', 'token_depth'];

      const RISK_M = ['prompt_injection', 'jailbreak_detection', 'unsafe_prompt', 'safety_validation', 'toxicity_score'];
      const GOV_M = ['secrets_found', 'secrets_blocked', 'files_scanned', 'pii_detection', 'entity_count', 'masking', 'policies_executed', 'policies_passed', 'policies_failed'];

      function metricGroup(m, r) {
        if (r && ['OpenLIT', 'OpenCost'].includes(r.resource_name)) return 'C';
        if (COST_M.includes(m))    return 'C';
        if (VALID_M.includes(m))   return 'V';
        if (QUALITY_M.includes(m)) return 'Q';
        if (PROD_M.includes(m))    return 'P';
        if (RISK_M.includes(m))    return 'R';
        if (GOV_M.includes(m))     return 'G';
        return 'other';
      }

      const knownResources = ["Langfuse", "Phoenix", "Traceloop", "Prometheus", "Grafana", "DeepEval", "Jaeger", "Zipkin", "LangSmith", "Ragas", "AgentOps", "OpenTelemetry", "Grafana Tempo", "Apache SkyWalking", "Rebuff", "LLMGuard", "TruLens", "Falco", "Sentry", "Detect-Secrets", "Microsoft Presidio", "Open Policy Agent", "Keycloak", "OpenMetadata", "OpenLIT", "OpenCost", "Guardrails AI", "Pydantic AI", "Instructor", "Confident AI"];
      const apiResources = Array.from(new Set((this._results || []).map(r => r.resource_name)));
      const activeResources = Array.from(new Set([...knownResources, ...apiResources]));
      const filteredResults = (this._results || []).filter(r => activeResources.includes(r.resource_name));

      // Group by resource → then by C/V/Q/P/R/G
      const byResource = {};
      for (const r of filteredResults) {
        if (!byResource[r.resource_name]) byResource[r.resource_name] = [];
        byResource[r.resource_name].push(r);
      }

      let rows = '';
      const GROUP_LABELS = {
        P: { label: '⚡ Productivity (P)', color: '#38bdf8', bg: 'rgba(56,189,248,0.08)'},
        C: { label: '💰 Cost (C)',       color: '#f97316', bg: 'rgba(249,115,22,0.08)' },
        V: { label: '✅ Validation (V)', color: '#22c55e', bg: 'rgba(34,197,94,0.08)'  },
        Q: { label: '🧬 Quality (Q)',    color: '#a78bfa', bg: 'rgba(167,139,250,0.08)'},
        R: { label: '🛡 Risk (R)',       color: '#f43f5e', bg: 'rgba(244,63,94,0.08)'  },
        G: { label: '⚖ Governance (G)', color: '#facc15', bg: 'rgba(250,204,21,0.08)'  },
      };

      for (const resourceName of activeResources) {
        const metrics = byResource[resourceName] || [];
        const detectedCount = metrics.filter(m => m.detected).length;
        const dashUrlData = RESOURCE_URLS[resourceName];
        const baseUrl = dashUrlData?.url;
        const isOnline = dashUrlData?.online !== false;
        const tcpOnline = dashUrlData?.online === true;

        // Build drill-through URL with agent filter
        let dashUrl = baseUrl;
        if (baseUrl && isOnline) {
          // If using the fallback backend metrics URL, just open it directly
          if (!baseUrl.includes("/metrics")) {
            if (resourceName === 'Prometheus') {
              dashUrl = `${baseUrl}/graph?g0.expr=dpi_ls_model_cost{agent_id="chandra-finops"}&g0.tab=0&g0.stacked=0&g0.range_input=1h`;
            } else if (resourceName === 'Grafana') {
              dashUrl = `${baseUrl}/d/dpi-ls-cost-001/dpi-ls-cost-dashboard-chandra-finops?orgId=1&var-agent=chandra-finops`;
            }
          }
        }

        let dashBtn = `<span style="font-size:11px;color:#6b7280">Disabled</span>`;
        if (dashUrl && isOnline) {
          if (tcpOnline) {
            dashBtn = `<button onclick="window.open('${dashUrl}','_blank')" style="padding:3px 10px;font-size:11px;font-weight:600;background:rgba(99,102,241,0.1);color:#818cf8;border:1px solid rgba(99,102,241,0.3);border-radius:6px;cursor:pointer">🔗 Open ${resourceName}</button>`;
          } else {
            dashBtn = `<button onclick="window.open('/widget/resources.html','_blank')" style="padding:3px 10px;font-size:11px;font-weight:600;background:rgba(56,189,248,0.1);color:#38bdf8;border:1px solid rgba(56,189,248,0.3);border-radius:6px;cursor:pointer">🔗 Open ${resourceName}</button>`;
          }
        }

        // Resource header row
        rows += `<tr style="background:rgba(15,23,42,0.6)">
          <td colspan="8" style="padding:10px 12px">
            <div style="display:flex;align-items:center;gap:12px">
              <span style="font-size:13px;font-weight:700;color:#e2e8f0">${escapeHtml(resourceName)}</span>
              <span style="font-size:11px;color:#64748b">${detectedCount}/${metrics.length} detected</span>
              ${dashBtn}
            </div>
          </td>
        </tr>`;

        if (metrics.length === 0) {
          rows += `<tr style="border-bottom:1px solid rgba(255,255,255,0.04)">
            <td colspan="8" style="padding:16px 12px;text-align:center;font-size:12px;color:#f87171;font-weight:600;font-style:italic">No Runtime Metrics Detected</td>
          </tr>`;
          continue;
        }

        // Render each group
        for (const [grpKey, grpInfo] of Object.entries(GROUP_LABELS)) {
          const grpMetrics = metrics.filter(m => metricGroup(m.metric, m) === grpKey);
          if (grpMetrics.length === 0) continue;

          // Group sub-header
          rows += `<tr style="background:${grpInfo.bg}">
            <td colspan="8" style="padding:5px 20px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:${grpInfo.color}">
              ${grpInfo.label}
            </td>
          </tr>`;

          for (const r of grpMetrics) {
            const niceName = METRIC_NICE[r.metric] || r.metric;
            const detectedHtml = r.detected
              ? `<span style="color:#34d399;font-weight:700">True ✓</span>`
              : `<span style="color:#f87171;font-weight:700">False ✗</span>`;
            const verifiedBtn = r.dashboard_verified
              ? `<span style="color:#34d399;font-weight:600">✓ Verified</span>`
              : `<button class="secondary verify-btn" data-resource="${escapeHtml(r.resource_name)}" data-metric="${escapeHtml(r.metric)}" style="padding:3px 8px;font-size:11px">Verify</button>`;
            const runTimeStr = r.last_run ? new Date(r.last_run).toLocaleTimeString() : '—';
            const statusPill = r.status === 'SUCCESS'
              ? `<span class="pill" style="color:#15803d;background:#dcfce7">SUCCESS</span>`
              : `<span class="pill" style="color:#b91c1c;background:#fee2e2">FAILED</span>`;

            rows += `<tr style="border-bottom:1px solid rgba(255,255,255,0.04)">
              <td style="padding:7px 12px 7px 28px;font-size:12px;color:#94a3b8">${escapeHtml(resourceName)}</td>
              <td style="padding:7px 10px;font-size:12px;font-weight:600;color:#cbd5e1">${escapeHtml(niceName)}</td>
              <td style="padding:7px 10px;font-size:12px;font-variant-numeric:tabular-nums;color:#e2e8f0">${escapeHtml(r.current_value || '0.0')}</td>
              <td style="padding:7px 10px;font-size:12px;text-align:center">${detectedHtml}</td>
              <td style="padding:7px 10px;font-size:11px;color:#64748b;max-width:260px;word-break:break-all">${escapeHtml(r.evidence || '')}</td>
              <td style="padding:7px 10px;font-size:11px;color:#64748b">${escapeHtml(runTimeStr)}</td>
              <td style="padding:7px 10px;text-align:center">${statusPill}</td>
              <td style="padding:7px 10px;text-align:center">${verifiedBtn}</td>
            </tr>`;
          }
        }
      }

      const tableHtml = `
        <div style="background:var(--card-bg);border:1px solid var(--border);border-radius:12px;padding:20px;box-shadow:0 1px 2px rgba(0,0,0,0.04);margin-bottom:24px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <div>
              <span style="font-size:13px;text-transform:uppercase;letter-spacing:0.05em;color:var(--muted);font-weight:600">Evaluation Matrix</span>
              <div style="font-size:11px;color:#64748b;margin-top:3px">
                DPI-LS Observability Stack &nbsp;|&nbsp;
                <span style="color:#f97316">C: Cost</span> &nbsp;·&nbsp;
                <span style="color:#22c55e">V: Validation</span> &nbsp;·&nbsp;
                <span style="color:#a78bfa">Q: Quality</span> &nbsp;·&nbsp;
                <span style="color:#94a3b8">P · E · G · R via Agent Dashboard</span>
              </div>
            </div>
            <button data-action="run-eval">Run Full Technical Evaluation</button>
          </div>
          <div style="overflow-x:auto">
            <table style="width:100%;border-collapse:collapse;text-align:left">
              <thead>
                <tr style="border-bottom:2px solid var(--border);color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:0.05em">
                  <th style="padding:10px">Resource</th>
                  <th style="padding:10px">Metric</th>
                  <th style="padding:10px">Value</th>
                  <th style="padding:10px;text-align:center">Detected</th>
                  <th style="padding:10px">Evidence</th>
                  <th style="padding:10px">Last Run</th>
                  <th style="padding:10px;text-align:center">Status</th>
                  <th style="padding:10px;text-align:center">Dashboard</th>
                </tr>
              </thead>
              <tbody>
                ${rows}
              </tbody>
            </table>
          </div>
        </div>
      `;
      this._renderShell(tableHtml);
    }
  }
  window.calculateCostMetrics = calculateCostMetrics;
  window.renderCostTableHtml = renderCostTableHtml;
  window.calculateValidationMetrics = calculateValidationMetrics;
  window.renderValidationTableHtml = renderValidationTableHtml;
  window.renderQualityTableHtml = renderQualityTableHtml;
  window.calculateProductivityMetrics = calculateProductivityMetrics;
  window.renderProductivityTableHtml = renderProductivityTableHtml;
  window.renderGovernanceTableHtml = renderGovernanceTableHtml;
  window.renderRiskTableHtml = renderRiskTableHtml;
  window.renderExecutionTableHtml = renderExecutionTableHtml;

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
  if (!customElements.get("dpi-ls-cost-evaluation")) {
    customElements.define("dpi-ls-cost-evaluation", DpiLsCostEvaluation);
  }
})();
