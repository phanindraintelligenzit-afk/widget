
const API = (typeof window !== 'undefined' && window.location?.origin && window.location.origin !== 'null')
  ? window.location.origin
  : '';
let chandraSub = {}; // validation sub-metrics
let chandraCostSub = {}; // cost sub-metrics
let settingsObj = {};
let chandraQualitySub = {}; // quality sub-metrics
let chandraCostValue = 1.0;
let chandraValidationValue = 1.0;
let chandraQualityValue = "Pending SME Review";
let chandraProductivitySub = {};
let chandraProductivityValue = 1.0;
let chandraExecutionSub = {};
let chandraExecutionValue = 1.0;
let chandraRiskSub = {};
let chandraRiskValue = 1.0;
let chandraGovSub = {};
let chandraGovValue = 1.0;
let allData = [];
let currentFilter = 'all';
// dashboardUrls stores {url, online} objects keyed by resource name
let dashboardUrls = {
  Langfuse:        { url: 'https://cloud.langfuse.com', online: false },
  Prometheus:      { url: 'http://localhost:9090', online: false },
  Grafana:         { url: 'http://localhost:3000', online: false },
  'DeepEval':      { url: 'https://deepeval.com', online: true },
  'Jaeger':        { url: 'http://localhost:16686', online: false },
  'Zipkin':        { url: 'http://localhost:9411', online: false },
  'LangSmith':     { url: 'https://smith.langchain.com', online: true },
  'Ragas':         { url: 'https://ragas.io', online: true },
  'AgentOps':      { url: 'https://app.agentops.ai', online: true },
  'OpenTelemetry': { url: 'http://localhost:16686', online: false },
  'Grafana Tempo': { url: 'http://localhost:3200', online: false },
  'Apache SkyWalking': { url: 'http://localhost:8080', online: false },
};

async function loadChandraData() {
  try {
    const [r1, r2] = await Promise.all([
      fetch(`${API}/ratings?all=true`),
      fetch(`${API}/settings`)
    ]);
    if (r1.ok) {
      const ratings = await r1.json();
      const chandra = ratings.find(r => r.agent_id === "chandra-finops");
      if (chandra) {
        chandraSub = chandra.sub_metrics?.V || {};
        chandraValidationValue = chandra.metrics?.V !== undefined ? chandra.metrics.V : 1.0;
        chandraCostSub = chandra.sub_metrics?.C || {};
        chandraCostValue = chandra.metrics?.C !== undefined ? chandra.metrics.C : 1.0;
        chandraQualitySub = chandra.sub_metrics?.Q || {};
        chandraQualityValue = chandra.metrics?.Q !== undefined ? chandra.metrics.Q : "Pending SME Review";
        chandraProductivitySub = chandra.sub_metrics?.P || {};
        chandraProductivityValue = chandra.metrics?.P !== undefined ? chandra.metrics.P : 1.0;
        chandraExecutionSub = chandra.sub_metrics?.E || {};
        chandraExecutionValue = chandra.metrics?.E !== undefined ? chandra.metrics.E : 1.0;
        chandraRiskSub = chandra.sub_metrics?.R || {};
        chandraRiskValue = chandra.metrics?.R !== undefined ? chandra.metrics.R : 1.0;
        chandraGovSub = chandra.sub_metrics?.G || {};
        chandraGovValue = chandra.metrics?.G !== undefined ? chandra.metrics.G : 1.0;
      }
    }
    if (r2.ok) {
      settingsObj = await r2.json();
    }
  } catch(e) {
    console.error("Failed to load Chandra ratings/settings for resources", e);
  }
}

async function loadUrls() {
  try {
    const [r1, r2, r3, r4, r5, r6, r7] = await Promise.all([
      fetch(`${API}/api/cost-evaluation/urls`),
      fetch(`${API}/api/validation-evaluation/urls`),
      fetch(`${API}/api/quality-evaluation/urls`),
      fetch(`${API}/api/productivity-evaluation/urls`),
      fetch(`${API}/api/execution-evaluation/urls`),
      fetch(`${API}/api/risk-evaluation/urls`),
      fetch(`${API}/api/governance-evaluation/urls`)
    ]);
    const processUrls = async (r) => {
      if (r.ok) {
        const raw = await r.json();
        for (const [name, val] of Object.entries(raw)) {
          if (val && typeof val === 'object' && 'url' in val) {
            dashboardUrls[name] = { url: val.url, online: val.online };
          } else {
            dashboardUrls[name] = { url: String(val), online: false };
          }
        }
      }
    };
    await Promise.all([
      processUrls(r1),
      processUrls(r2),
      processUrls(r3),
      processUrls(r4),
      processUrls(r5),
      processUrls(r6),
      processUrls(r7)
    ]);
  } catch (e) {
    console.error("Failed to load urls", e);
  }
}

const RESOURCE_META = {

  'Guardrails AI': {
    name: 'Guardrails AI', icon: '🛡️', category: 'Validation', dpi_status: 'primary',
    description: 'Structural validation and schema enforcement.',
    dashboard_url: 'https://www.guardrailsai.com/docs', dashboard_label: 'Open Guardrails',
    sdk: 'guardrails-ai'
  },
  
  'Confident AI': {
    name: 'Confident AI', icon: '🧠', category: 'Quality', dpi_status: 'primary',
    description: 'Unit testing and evaluation for LLMs (DeepEval)',
    dashboard_url: 'https://docs.confident-ai.com', dashboard_label: 'Open Confident AI',
    sdk: 'deepeval'
  },
  'Pydantic AI': {
    name: 'Pydantic AI', icon: '✨', category: 'Validation', dpi_status: 'primary',
    description: 'Type-safe parsing and validation.',
    dashboard_url: 'https://ai.pydantic.dev', dashboard_label: 'Open Pydantic AI',
    sdk: 'pydantic-ai'
  },
  'Instructor': {
    name: 'Instructor', icon: '🎓', category: 'Validation', dpi_status: 'primary',
    description: 'Structured output validation for LLMs.',
    dashboard_url: 'https://python.useinstructor.com', dashboard_label: 'Open Instructor',
    sdk: 'instructor'
  },

  "LLMGuard": {
    name: 'LLMGuard',
    icon: '🛡️', category: 'Risk & Security',
    description: 'Comprehensive security scanner for LLM prompts and responses.',
    tags: ['Security', 'Prompt Injection', 'Toxicity']
  },
  "TruLens": {
    name: 'TruLens',
    icon: '🔬', category: 'Risk & Security',
    description: 'Evaluation and tracking for LLM apps, focusing on groundedness and relevance.',
    tags: ['Evaluation', 'Relevance', 'Tracking']
  },
  "Rebuff": {
    name: 'Rebuff',
    icon: '🛡️', category: 'Risk & Security',
    description: 'Prompt injection detection and mitigation.',
    tags: ['Security', 'Injection', 'Defense']
  },
  "Open Policy Agent": {
    name: 'Open Policy Agent',
    icon: '📜', category: 'Governance',
    description: 'Cloud-native policy engine that unifies policy enforcement across the stack.',
    tags: ['Policy', 'Rules', 'Runtime']
  },
  "Microsoft Presidio": {
    name: 'Microsoft Presidio',
    icon: '🕵️', category: 'Governance',
    description: 'Data protection and de-identification SDK for text and images.',
    tags: ['PII', 'Anonymization', 'Data Privacy']
  },
  "Detect-Secrets": {
    name: 'Detect-Secrets',
    icon: '🔑', category: 'Governance',
    description: 'Enterprise secrets scanning to prevent credential leakage.',
    tags: ['Secrets', 'Scanning', 'Compliance']
  },
  "Open Policy Agent": {
    name: 'Open Policy Agent',
    icon: '📜', category: 'Governance',
    description: 'Cloud-native policy engine that unifies policy enforcement across the stack.',
    tags: ['Policy', 'Rules', 'Runtime']
  },
  "Microsoft Presidio": {
    name: 'Microsoft Presidio',
    icon: '🕵️', category: 'Governance',
    description: 'Data protection and de-identification SDK for text and images.',
    tags: ['PII', 'Anonymization', 'Data Privacy']
  },
  "Detect-Secrets": {
    name: 'Detect-Secrets',
    icon: '🔑', category: 'Governance',
    description: 'Enterprise secrets scanning to prevent credential leakage.',
    tags: ['Secrets', 'Scanning', 'Compliance']
  },
  'Phoenix': {
    icon: '🔥', category: 'Execution Metrics',
    dpi_status: 'primary',
    description: 'Tracks full execution details, step-by-step telemetry, and spans. Traces are pushed dynamically during execution.',
    dashboard_url: 'http://localhost:6006',
    dashboard_label: 'Open Phoenix Dashboard',
    color: '#eab308',
    sdk: 'arize-phoenix',
  },
  'Traceloop': {
    icon: '🔁', category: 'Execution Metrics',
    dpi_status: 'primary',
    description: 'Tracks loop completion, retry counts, execution stability, and LLM orchestration telemetry.',
    dashboard_url: 'https://app.traceloop.com',
    dashboard_label: 'Open Traceloop Dashboard',
    color: '#3b82f6',
    sdk: 'traceloop-sdk',
  },
  'Langfuse': {
    icon: '🔭', category: 'LLM Observability',
    dpi_status: 'primary',
    description: 'Token usage, cost per trace/generation, model spend, and latency per LLM call. Traces are pushed automatically on every agent run.',
    dashboard_url: 'https://cloud.langfuse.com',
    dashboard_label: 'Open Langfuse Cloud',
    color: '#6366f1',
    sdk: 'langfuse',
  },
  'Prometheus': {
    icon: '📊', category: 'Infrastructure Metrics',
    dpi_status: 'recommended',
    description: 'Live Prometheus-format metrics for Chandra FinOps agent — token costs, model cost, TCO, quality scores, and utilization. Exposed by DPI-LS at /metrics/.',
    dashboard_url: 'http://127.0.0.1:8000/metrics/',
    dashboard_label: 'Open Metrics Endpoint',
    color: '#e6522c',
    sdk: 'prometheus_client',
  },
  'Grafana': {
    icon: '📈', category: 'Metrics Visualization',
    dpi_status: 'recommended',
    description: 'Visualization of cost and utilization metrics. Import grafana_dashboard.json from the widget folder to see DPI-LS dashboards.',
    dashboard_url: 'https://grafana.com/auth/sign-in/',
    dashboard_label: 'Open Grafana Cloud',
    color: '#f46800',
    sdk: 'grafana',
  },
  'OpenLIT': {
    icon: '🔥', category: 'LLM Observability',
    dpi_status: 'primary',
    description: 'Tracks comprehensive metrics for LLM observability including tokens, latency, cost, and provider details.',
    dashboard_url: 'http://localhost:3000',
    dashboard_label: 'Open OpenLIT',
    color: '#ff4d4d',
    sdk: 'openlit',
  },
  'OpenCost': {
    icon: '💸', category: 'Infrastructure Metrics',
    dpi_status: 'primary',
    description: 'Tracks infrastructure cost mapping to cluster nodes, pods, and assets.',
    dashboard_url: 'http://localhost:9003',
    dashboard_label: 'Open OpenCost',
    color: '#10b981',
    sdk: 'requests',
  },
  'DeepEval': {
    icon: '🔮', category: 'LLM Eval & Validation',
    dpi_status: 'primary',
    description: 'Calculates Answer Relevancy, Faithfulness, Hallucination, Correctness, and Evaluation Status directly from agent outputs.',
    dashboard_url: 'https://deepeval.com',
    dashboard_label: 'Open DeepEval',
    color: '#ff4d4d',
    sdk: 'deepeval',
  },
  'Jaeger': {
    icon: '🔍', category: 'Distributed Tracing & Observability',
    dpi_status: 'foundational',
    description: 'Monitors validation service traces, latency, span counts, and error rates. Provides deep visibility into validation runtime behavior.',
    dashboard_url: 'http://localhost:16686',
    dashboard_label: 'Open Jaeger UI',
    color: '#60dea9',
    sdk: 'opentelemetry',
  },
  'Zipkin': {
    icon: '⚡', category: 'Distributed Tracing',
    dpi_status: 'foundational',
    description: 'Tracks trace timelines, service calls, and latency. Provides a comprehensive view of execution duration.',
    dashboard_url: 'http://localhost:9411',
    dashboard_label: 'Open Zipkin UI',
    color: '#ff9800',
    sdk: 'opentelemetry',
  },
  'LangSmith': {
    icon: '🦜', category: 'LLM Observability',
    dpi_status: 'primary',
    description: 'Calculates runtime traces, LLM evaluation, hallucination analysis, prompt evaluation, and context evaluation.',
    dashboard_url: 'https://smith.langchain.com',
    dashboard_label: 'Open LangSmith',
    color: '#1c1c1c',
    sdk: 'langsmith',
  },
  'Ragas': {
    icon: '🔍', category: 'LLM Eval & Validation',
    dpi_status: 'primary',
    description: 'Calculates Semantic Accuracy, Faithfulness, Answer Relevancy, Context Precision, and Context Recall.',
    dashboard_url: 'https://ragas.io',
    dashboard_label: 'Open Ragas',
    color: '#e74c3c',
    sdk: 'ragas',
  },
  'AgentOps': {
    icon: '🤖', category: 'Agent Observability',
    dpi_status: 'primary',
    description: 'Calculates runtime execution history, agent behaviour, consistency measurement, session metrics, and stability metrics.',
    dashboard_url: 'https://app.agentops.ai',
    dashboard_label: 'Open AgentOps',
    color: '#2980b9',
    sdk: 'agentops',
  },
  'OpenTelemetry': {
    icon: '🌐', category: 'Distributed Tracing',
    dpi_status: 'foundational',
    description: 'Calculates Worker Concurrency, Decision Branches, and Human Baseline for productivity scoring.',
    dashboard_url: 'http://localhost:16686',
    dashboard_label: 'Open OpenTelemetry UI',
    color: '#3498db',
    sdk: 'opentelemetry',
  },
  'Grafana Tempo': {
    icon: '⏱️', category: 'Distributed Tracing',
    dpi_status: 'primary',
    description: 'Tracks API calls, execution duration, and resolution velocity across asynchronous LLM tasks.',
    dashboard_url: 'https://grafana.com/oss/tempo/',
    dashboard_label: 'Open Grafana Tempo',
    color: '#e67e22',
    sdk: 'opentelemetry',
  },
  'Apache SkyWalking': {
    icon: '🦅', category: 'Application Performance Monitoring',
    dpi_status: 'primary',
    description: 'Monitors Token Depth, Throughput, and traces productivity bottlenecks in real-time.',
    dashboard_url: 'https://skywalking.apache.org/',
    dashboard_label: 'Open Apache SkyWalking',
    color: '#2c3e50',
    sdk: 'opentelemetry',
  },
};


const STATUS_ORDER = { primary: 0, foundational: 1, recommended: 2, candidate: 3, optional: 4 };

function statusBadgeClass(status) {
  const map = { primary:'badge-primary', foundational:'badge-primary', recommended:'badge-recommended', candidate:'badge-candidate', optional:'badge-optional' };
  return map[status] || 'badge-optional';
}
function statusLabel(status) {
  const map = { primary:'⭐ Primary', foundational:'🔧 Foundational', recommended:'💡 Recommended', candidate:'🧪 Candidate', optional:'Optional' };
  return map[status] || status;
}

// Group results by resource_name
function groupByResource(data) {
  const map = {};
  for (const item of data) {
    if (!map[item.resource_name]) map[item.resource_name] = [];
    map[item.resource_name].push(item);
  }
  return map;
}

// Determine overall status per resource
function resourceStatus(name, metrics = []) {
  const dashInfo = dashboardUrls[name] || { url: '', online: true };
  if (!dashInfo.online) return 'failed';
  
  if (metrics.some(m => m.status === 'CREDENTIALS_MISSING')) return 'failed';
  const ok = metrics.filter(m => m.status === 'SUCCESS').length;
  if (ok > 0) return 'success';
  return 'failed';
}

// Which evaluation step is complete for a resource
function computeSteps(metrics) {
  const agentRan = metrics.some(m => m.agent_executed);
  
  // Real evidence excludes the bootstrap placeholder messages
  const hasEvidence = metrics.some(m => m.evidence && m.evidence.length > 10 && !m.evidence.includes('Integration ready'));
  const detected = metrics.some(m => m.detected);
  const dashVerified = metrics.some(m => m.dashboard_verified);
  
  const step1 = true;
  const step2 = agentRan;
  const step3 = step2 && hasEvidence;
  const step4 = step3 && detected;
  const step5 = (step4 || dashVerified);
  
  return [step1, step2, step3, step4, step5];
}

function escHtml(str) {
  return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function renderStepsTrack(steps) {
  const labels = ['Setup','Instrument','Execute','Validate','Document'];
  let html = '<div class="steps-track">';
  for (let i = 0; i < 5; i++) {
    const done = steps[i];
    const active = !done && (i === 0 || steps[i-1]);
    const cls = done ? 'done' : (active ? 'active' : 'pending');
    html += `<div class="step-node">
      <div class="step-circle ${cls}">${done ? '✓' : (i+1)}</div>
      <div class="step-name ${cls}">${labels[i]}</div>
    </div>`;
    if (i < 4) {
      html += `<div class="step-connector ${done && steps[i+1] ? 'done' : ''}"></div>`;
    }
  }
  html += '</div>';
  return html;
}

const COST_METRICS     = ['input_tokens', 'output_tokens', 'model_cost', 'prompt_cost', 'completion_cost', 'ai_cost_per_output', 'human_cost_per_output', 'utilization', 'efficiency_ratio', 'cost_score', 'tco'];
const VALIDATION_METRICS = ['validated_components','required_components','validation_score'];
const QUALITY_METRICS  = ['hallucination_score','relevance_score','groundedness_score','user_feedback_score','model_correctness'];

const METRIC_NICE_NAMES = {
  input_tokens: 'Input Tokens',
  output_tokens: 'Output Tokens',
  model_cost: 'Model Cost',
  prompt_cost: 'Prompt Cost',
  completion_cost: 'Completion Cost',
  ai_cost_per_output: 'AI Cost / Output',
  human_cost_per_output: 'Human Cost / Output',
  utilization: 'Utilization',
  efficiency_ratio: 'Efficiency Ratio',
  cost_score: 'Cost Score',
  tco: 'Total Cost (TCO)',
  validated_components: 'Validated Components',
  required_components: 'Required Components',
  validation_score: 'Validation Score',
  hallucination_score: 'Hallucination Score',
  relevance_score: 'Relevance Score',
  consistency: 'Consistency',
  user_feedback_score: 'User Feedback Score',
  model_correctness: 'Model Correctness',
};

function formatMetricValue(metric, current_value) {
  if (current_value === null || current_value === undefined || current_value === "") return '—';
  return current_value;
}

function renderResourceTable(metrics, name) {
  if (!metrics || metrics.length === 0) {
    return `<div style="padding:16px 12px;text-align:center;font-size:12px;color:#f87171;font-weight:600;font-style:italic">No Runtime Metrics Detected</div>`;
  }

  const liveMetrics = {};
  metrics.forEach(m => {
    liveMetrics[m.metric] = m.current_value;
  });

  if (['Prometheus', 'Grafana', 'OpenCost', 'OpenLIT'].includes(name)) {
    if (typeof window.renderCostTableHtml === 'function') {
      const mergedSub = { ...chandraCostSub, ...liveMetrics };
      return window.renderCostTableHtml(mergedSub, settingsObj, chandraCostValue, name);
    }
  } else if (['LangSmith', 'Ragas', 'AgentOps'].includes(name)) {
    if (typeof window.renderQualityTableHtml === 'function') {
      const mergedSub = { ...chandraQualitySub, ...liveMetrics };
      return window.renderQualityTableHtml(mergedSub, settingsObj, chandraQualityValue, name);
    }
  } else if (['OpenTelemetry', 'Grafana Tempo', 'Apache SkyWalking'].includes(name)) {
    if (typeof window.renderProductivityTableHtml === 'function') {
      const mergedSub = { ...chandraProductivitySub, ...liveMetrics };
      return window.renderProductivityTableHtml(mergedSub, settingsObj, chandraProductivityValue, name);
    }
  } else if (['Langfuse', 'Phoenix', 'Traceloop'].includes(name)) {
    if (name === 'Langfuse') {
      // Langfuse spans both Cost and Execution — render both sections
      const costMetrics  = metrics.filter(m => m._dimension === 'cost' || (!m._dimension && ['input_tokens','output_tokens','prompt_cost','total_cost','model_cost','trace_cost','cost_per_output'].some(k => m.metric && m.metric.includes(k))));
      const execMetrics  = metrics.filter(m => m._dimension === 'execution' || (!m._dimension && !costMetrics.includes(m)));
      let html = '';
      if (costMetrics.length && typeof window.renderCostTableHtml === 'function') {
        const costSub = {};
        costMetrics.forEach(m => { costSub[m.metric] = m.current_value; });
        const mergedCost = { ...chandraCostSub, ...costSub };
        html += `<div style="margin-bottom:16px;"><div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">💰 Cost Metrics</div>${window.renderCostTableHtml(mergedCost, settingsObj, chandraCostValue, name)}</div>`;
      }
      if (execMetrics.length) {
        const execRows = execMetrics.map(m => `
          <tr>
            <td style="padding:6px 8px;color:var(--text);font-size:12px;">${escHtml(m.metric)}</td>
            <td style="padding:6px 8px;color:var(--accent);font-size:12px;">${escHtml(String(m.current_value))}</td>
            <td style="padding:6px 8px;color:var(--muted);font-size:11px;">${escHtml(m.evidence || '')}</td>
          </tr>`).join('');
        html += `<div><div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">⚡ Execution Metrics</div>
          <table style="width:100%;border-collapse:collapse;font-size:12px;">
            <thead><tr style="border-bottom:1px solid var(--border);">
              <th style="padding:6px 8px;text-align:left;color:var(--muted);font-weight:600;">Metric</th>
              <th style="padding:6px 8px;text-align:left;color:var(--muted);font-weight:600;">Value</th>
              <th style="padding:6px 8px;text-align:left;color:var(--muted);font-weight:600;">Evidence</th>
            </tr></thead><tbody>${execRows}</tbody></table></div>`;
      }
      return html || `<div style="padding:10px;color:var(--muted);">No metrics captured yet.</div>`;
    }
    // Phoenix / Traceloop — execution only
    if (typeof window.renderExecutionTableHtml === 'function') {
      const mergedSub = { ...chandraExecutionSub, ...liveMetrics };
      return window.renderExecutionTableHtml(mergedSub, settingsObj, chandraExecutionValue, name);
    }
    const rows = metrics.map(m => `
      <tr>
        <td style="padding:6px 8px;color:var(--text);font-size:12px;">${escHtml(m.metric)}</td>
        <td style="padding:6px 8px;color:var(--accent);font-size:12px;">${escHtml(String(m.current_value))}</td>
        <td style="padding:6px 8px;color:var(--muted);font-size:11px;">${escHtml(m.evidence || '')}</td>
      </tr>`).join('');
    return `<table style="width:100%;border-collapse:collapse;font-size:12px;">
      <thead><tr style="border-bottom:1px solid var(--border);">
        <th style="padding:6px 8px;text-align:left;color:var(--muted);font-weight:600;">Metric</th>
        <th style="padding:6px 8px;text-align:left;color:var(--muted);font-weight:600;">Value</th>
        <th style="padding:6px 8px;text-align:left;color:var(--muted);font-weight:600;">Evidence</th>
      </tr></thead><tbody>${rows}</tbody></table>`;
  } else if (['DeepEval', 'Jaeger', 'Zipkin'].includes(name)) {
    if (typeof window.renderValidationTableHtml === 'function') {
      const mergedSub = { ...chandraSub, ...liveMetrics };
      return window.renderValidationTableHtml(mergedSub, settingsObj, chandraValidationValue, name);
    }
    return `<div style="padding:15px;color:#64748b;">Validation rendering logic missing.</div>`;
  } else if (['Open Policy Agent', 'Microsoft Presidio', 'Detect-Secrets'].includes(name)) {
    if (typeof window.renderGovernanceTableHtml === 'function') {
      const mergedSub = { ...chandraGovSub, ...liveMetrics };
      return window.renderGovernanceTableHtml(mergedSub, settingsObj, chandraGovValue, name);
    }
    return `<div style="padding:15px;color:#64748b;">Governance rendering logic missing.</div>`;
  } else if (['LLMGuard', 'Rebuff', 'TruLens'].includes(name)) {
    if (typeof window.renderRiskTableHtml === 'function') {
      const mergedSub = { ...chandraRiskSub, ...liveMetrics };
      return window.renderRiskTableHtml(mergedSub, settingsObj, chandraRiskValue, name);
    }
  } else {
    const rows = metrics.map(m => `
      <tr>
        <td style="padding:6px 8px;color:var(--text);font-size:12px;">${escHtml(m.metric)}</td>
        <td style="padding:6px 8px;color:var(--accent);font-size:12px;">${escHtml(String(m.current_value))}</td>
        <td style="padding:6px 8px;color:var(--muted);font-size:11px;">${escHtml(m.evidence || '')}</td>
      </tr>`).join('');
    return `<div><div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">✅ ${name} Metrics</div>
      <table style="width:100%;border-collapse:collapse;font-size:12px;">
      <thead><tr style="border-bottom:1px solid var(--border);">
        <th style="padding:6px 8px;text-align:left;color:var(--muted);font-weight:600;">Metric</th>
        <th style="padding:6px 8px;text-align:left;color:var(--muted);font-weight:600;">Value</th>
        <th style="padding:6px 8px;text-align:left;color:var(--muted);font-weight:600;">Evidence</th>
      </tr></thead><tbody>${rows || `<tr><td colspan="3" style="padding:6px 8px;color:var(--muted);text-align:center;">No metrics captured yet.</td></tr>`}</tbody></table></div>`;
  }
  return `<div style="padding:10px;color:var(--muted);">Rendering table…</div>`;
}

function toggleResourceTable(name) {
  const container = document.querySelector(`.table-container-${name}`);
  const arrow = document.querySelector(`.arrow-${name}`);
  if (container) {
    if (container.style.display === 'none') {
      container.style.display = 'block';
      arrow.textContent = '▼';
    } else {
      container.style.display = 'none';
      arrow.textContent = '▶';
    }
  }
}

function renderResourceCard(name, metrics = []) {
  const meta = RESOURCE_META[name] || { icon:'📦', category:'Unknown', dpi_status:'optional', description:'', dashboard_url:null, dashboard_label:name, color:'#6366f1' };
  const overallStatus = resourceStatus(name, metrics);
  const steps = computeSteps(metrics);
  const stepsCompleted = steps.filter(Boolean).length;
  const detectedCount = metrics.filter(m => m.detected).length;
  const lastRun = metrics[0]?.last_run ? new Date(metrics[0].last_run).toLocaleString() : '—';
  const dashVerified = metrics.some(m => m.dashboard_verified);
  const hasEvidence = metrics.some(m => m.evidence && m.evidence.length > 10);
  const statusClass = `status-${overallStatus}`;

  let statusCardBadge;
  if (overallStatus === 'success')      { statusCardBadge = 'badge-success'; }
  else if (overallStatus === 'failed')  { statusCardBadge = 'badge-failed'; }
  else                                   { statusCardBadge = 'badge-partial'; }

  const dashInfo = dashboardUrls[name] || { url: '', online: false };
  const dashUrl  = dashInfo.url || '';
  // Link is shown whenever evaluation passed (SUCCESS or PARTIAL).
  // TCP reachability only adds a small live-status indicator — it never hides the link.
  const isOnline = overallStatus !== 'failed';
  const tcpOnline = dashInfo.online;
  const liveTag = tcpOnline
    ? `<span title="Port reachable" style="font-size:10px;color:#4ade80;margin-left:6px;">● Live</span>`
    : `<span title="Port not reachable locally" style="font-size:10px;color:#f59e0b;margin-left:6px;">● Local port down</span>`;
  
  const nameHtml = `<span onclick="toggleResourceTable('${escHtml(name)}')" style="color:var(--text); text-decoration:underline dashed var(--muted); cursor:pointer;">${escHtml(name)}</span>`;

  let linkHtml;
  if (name === 'DeepEval') {
    linkHtml = `<a class="rc-dashboard-link-inline" href="https://deepeval.com" target="_blank" style="color:var(--accent); font-weight:700; text-decoration:underline; font-size:13px; display:inline-flex; align-items:center; gap:4px;">🔮 DeepEval Documentation</a><span style="font-size:10px;color:#4ade80;margin-left:6px;">● Running In Process</span>`;
  } else {
    const serviceOfflineStatus = ['LangSmith', 'Ragas', 'AgentOps'].includes(name) 
      ? `<span style="color:var(--muted2); font-weight:700; font-size:13px;">⚠️ Configuration Required</span>` 
      : `<span style="color:var(--muted2); font-weight:700; font-size:13px;">⚠️ Service Offline</span>`;

    linkHtml = (isOnline && tcpOnline)
      ? `<a class="rc-dashboard-link-inline" href="${dashUrl}" target="_blank" style="color:var(--accent); font-weight:700; text-decoration:underline; font-size:13px; display:inline-flex; align-items:center; gap:4px;">🔗 Open ${escHtml(name)}</a>${liveTag}`
      : (isOnline && !tcpOnline)
        ? `<button onclick="toggleResourceTable('${escHtml(name)}')" class="rc-dashboard-link-inline" style="background:none; border:none; cursor:pointer; padding:0; color:var(--accent); font-weight:700; text-decoration:underline; font-size:13px; display:inline-flex; align-items:center; gap:4px;">🔗 Open ${escHtml(name)}</button>${liveTag}`
        : serviceOfflineStatus;
  }


  const verifyHtml = dashVerified
    ? `<span class="verified-tag" style="color:var(--green); font-weight:bold; font-size:12px;">✅ Dashboard Verified</span>`
    : `<button class="verify-btn-card" onclick="verifyDashboard('${escHtml(name)}')">Mark Verified</button>`;

  const statusLabel2 = overallStatus === 'success' ? 'SUCCESS' : overallStatus === 'failed' ? 'FAILED' : 'PARTIAL';

  return `
    <div class="resource-card ${statusClass}" data-resource="${escHtml(name)}" data-status="${overallStatus}" data-dpi-status="${meta.dpi_status}">
      <!-- Header -->
      <div class="rc-header">
        <div class="rc-icon" style="background:${meta.color}22;">${meta.icon}</div>
        <div class="rc-title-group">
          <div class="rc-name">${nameHtml}</div>
          <div class="rc-category">${escHtml(meta.category)}</div>
          <div style="font-size:11px;color:var(--muted2);margin-top:3px;line-height:1.4">${escHtml(meta.description)}</div>
        </div>
        <div class="rc-badge">
          <span class="badge ${statusCardBadge}">${statusLabel2}</span>
          <span class="badge ${statusBadgeClass(meta.dpi_status)}">${statusLabel(meta.dpi_status)}</span>
        </div>
      </div>

      <!-- 5-Step Mini Progress -->
      <div class="rc-steps">
        <div class="rc-steps-label">Technical Evaluation Workflow — ${stepsCompleted}/5 Steps Complete</div>
        ${renderStepsTrack(steps)}
      </div>

      <!-- Metrics Table -->
      <div class="rc-metrics" style="margin-top: 15px;">
        <button class="toggle-table-btn" onclick="toggleResourceTable('${escHtml(name)}')" style="width:100%; text-align:left; background:rgba(255,255,255,0.05); border:1px solid var(--border); padding:8px 12px; border-radius:6px; color:var(--text); cursor:pointer; font-weight:bold; font-size:12px; display:flex; align-items:center; justify-content:space-between; outline:none; transition: background 0.2s;">
          <span>📊 ${
            name === 'Langfuse' ? 'Cost & Execution'
            : meta.category === 'Execution Metrics' ? 'Execution'
            : meta.category.includes('Validation') ? 'Validation'
            : ['Infrastructure Metrics', 'Metrics Visualization'].includes(meta.category) ? 'Cost'
            : ['Distributed Tracing', 'Application Performance Monitoring'].includes(meta.category) ? 'Productivity'
            : ['LLM Observability'].includes(meta.category) ? 'Execution'
            : ['Risk & Security', 'Data Privacy', 'Secrets Management', 'Policy Enforcement'].includes(meta.category) ? 'Governance & Risk'
            : 'Quality'
          } Details & Traceability (${detectedCount}/${metrics.length} Detected)</span>
          <span class="arrow-${escHtml(name)}">▼</span>
        </button>
        <div class="table-container-${escHtml(name)}" style="display:block; margin-top:12px; overflow-x:auto; width:100%;">
          ${renderResourceTable(metrics, name)}
          ${hasEvidence ? `<div style="margin-top:12px; padding:10px; background:#0f172a; border:1px solid #1e293b; border-radius:6px;">
            <div style="font-size:10px; color:#94a3b8; text-transform:uppercase; margin-bottom:4px; font-weight:700;">Final Runtime Evidence Payload</div>
            <code style="font-size:11px; color:#4ade80; font-family:'Courier New', monospace;">${escHtml(metrics.find(m => m.evidence && m.evidence.length > 10).evidence)}</code>
          </div>` : ''}
        </div>
      </div>

      <!-- Footer -->
      <div class="rc-footer" style="margin-top: 20px; display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; gap: 8px;">
          ${linkHtml}
          ${verifyHtml}
        </div>
        <div class="rc-last-run">Last run: ${escHtml(lastRun)}</div>
      </div>
    </div>
  `;
}

function setFilter(filter, btn) {
  currentFilter = filter;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  applyFilter();
}

function applyFilter() {
  const cards = document.querySelectorAll('.resource-card');
  cards.forEach(card => {
    let show = true;
    if (currentFilter === 'success')     show = card.dataset.status === 'success';
    else if (currentFilter === 'failed') show = card.dataset.status === 'failed';
    else if (currentFilter === 'primary')      show = ['primary','foundational'].includes(card.dataset.dpiStatus);
    else if (currentFilter === 'recommended')  show = card.dataset.dpiStatus === 'recommended';
    
    card.style.display = show ? '' : 'none';
    const nextEl = card.nextElementSibling;
    if (nextEl && nextEl.classList.contains('table-container-' + card.dataset.resource)) {
      if (!show) {
        nextEl.style.display = 'none';
        // Also reset the arrow
        const arrow = card.querySelector('.arrow-' + card.dataset.resource);
        if (arrow) arrow.textContent = '▶';
      }
    }
  });
}

function showToast(msg, type='info') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = `toast toast-${type} show`;
  setTimeout(() => { t.classList.remove('show'); }, 3500);
}

async function verifyDashboard(resourceName) {
  try {
    const isCost = ['Prometheus', 'Grafana'].includes(resourceName);
    const isQual = ['LangSmith', 'Ragas', 'AgentOps'].includes(resourceName);
    const isProd = ['OpenTelemetry', 'Grafana Tempo', 'Apache SkyWalking'].includes(resourceName);
    const isExec = ['Langfuse', 'Phoenix', 'Traceloop'].includes(resourceName);
    
    let endpoint = '/api/validation-evaluation/verify-dashboard';
    if (isCost) endpoint = '/api/cost-evaluation/verify-dashboard';
    if (isQual) endpoint = '/api/quality-evaluation/verify-dashboard';
    if (isProd) endpoint = '/api/productivity-evaluation/verify-dashboard';
    if (isExec) endpoint = '/api/execution-evaluation/verify-dashboard';
    
    const body = isCost ? { resource_name: resourceName, metric: 'model_cost' } : { resource_name: resourceName };
    const r = await fetch(`${API}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    showToast(`✅ ${resourceName} marked as dashboard verified!`, 'success');
    await loadData();
  } catch (e) {
    showToast(`Error: ${e.message}`, 'error');
  }
}

async function runEvaluation() {
  const btn = document.getElementById('run-eval-btn');
  btn.disabled = true;
  btn.textContent = '⏳ Running…';
  showToast('Running full technical evaluation across all resources…', 'info');
  try {
    const [r1, r2, r3, r4, r5, r6, r7] = await Promise.all([
      fetch(`${API}/api/cost-evaluation/evaluate`, { method: 'POST', headers: { 'Accept': 'application/json' } }),
      fetch(`${API}/api/validation-evaluation/evaluate`, { method: 'POST', headers: { 'Accept': 'application/json' } }),
      fetch(`${API}/api/quality-evaluation/evaluate`, { method: 'POST', headers: { 'Accept': 'application/json' } }),
      fetch(`${API}/api/productivity-evaluation/evaluate`, { method: 'POST', headers: { 'Accept': 'application/json' } }),
      fetch(`${API}/api/execution-evaluation/evaluate`, { method: 'POST', headers: { 'Accept': 'application/json' } }),
      fetch(`${API}/api/risk-evaluation/evaluate`, { method: 'POST', headers: { 'Accept': 'application/json' } }),
      fetch(`${API}/api/governance-evaluation/evaluate`, { method: 'POST', headers: { 'Accept': 'application/json' } })
    ]);
    if (!r1.ok || !r2.ok || !r3.ok || !r4.ok || !r5.ok) throw new Error(`HTTP Error during evaluation`);
    await loadChandraData();
    const [costData, valData, qualData, prodData, execData, riskData, govData] = await Promise.all([r1.json(), r2.json(), r3.json(), r4.json(), r5.json(), r6.json(), r7.json()]);
    const costResources = ["Langfuse", "Grafana", "Prometheus", "OpenLIT", "OpenCost"];
    const valResources = ["DeepEval", "Jaeger", "Zipkin", "Guardrails AI", "Pydantic AI", "Instructor"];
    const qualResources = ["LangSmith", "Ragas", "AgentOps", "Confident AI", "TruLens"];
    const prodResources = ["OpenTelemetry", "Apache SkyWalking", "Langfuse", "Prometheus"];
    const execResources = ["Langfuse", "Phoenix", "Traceloop"];
    const riskResources = ["Rebuff", "LLMGuard", "TruLens"];
    const govResources = ["Detect-Secrets", "Microsoft Presidio", "Open Policy Agent"];
    // Tag Langfuse cost rows so they can be distinguished from execution rows
    const langfuseCostRows = costData
      .filter(r => r.resource_name === 'Langfuse')
      .map(r => ({ ...r, _dimension: 'cost' }));
    const langfuseExecRows = execData
      .filter(r => r.resource_name === 'Langfuse')
      .map(r => ({ ...r, _dimension: 'execution' }));
    allData = [
      ...costData.filter(r => costResources.includes(r.resource_name)),
      ...valData.filter(r => valResources.includes(r.resource_name)),
      ...qualData.filter(r => qualResources.includes(r.resource_name)),
      ...prodData.filter(r => prodResources.includes(r.resource_name)),
      ...langfuseCostRows,
      ...langfuseExecRows,
      ...execData.filter(r => ['Phoenix', 'Traceloop'].includes(r.resource_name)),
      ...riskData.filter(r => riskResources.includes(r.resource_name)),
      ...govData.filter(r => govResources.includes(r.resource_name))
    ];
    renderGrid();
    showToast(`✅ Evaluation complete — ${allData.length} metrics evaluated!`, 'success');
  } catch (e) {
    showToast(`Evaluation failed: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '▶ Run Evaluation';
  }
}

async function loadData() {
  try {
    await loadChandraData();
    const [r1, r2, r3, r4, r5, r6, r7] = await Promise.all([
      fetch(`${API}/api/cost-evaluation/results`, { headers: { Accept: 'application/json' } }),
      fetch(`${API}/api/validation-evaluation/results`, { headers: { Accept: 'application/json' } }),
      fetch(`${API}/api/quality-evaluation/results`, { headers: { Accept: 'application/json' } }),
      fetch(`${API}/api/productivity-evaluation/results`, { headers: { Accept: 'application/json' } }),
      fetch(`${API}/api/execution-evaluation/results`, { headers: { Accept: 'application/json' } }),
      fetch(`${API}/api/risk-evaluation/results`, { headers: { Accept: 'application/json' } }),
      fetch(`${API}/api/governance-evaluation/results`, { headers: { Accept: 'application/json' } })
    ]);
    if (!r1.ok || !r2.ok || !r3.ok || !r4.ok || !r5.ok || !r6.ok || !r7.ok) throw new Error(`HTTP Error loading results`);
    const [costData, valData, qualData, prodData, execData, riskData, govData] = await Promise.all([r1.json(), r2.json(), r3.json(), r4.json(), r5.json(), r6.json(), r7.json()]);
    const costResources = ["Langfuse", "Grafana", "Prometheus", "OpenLIT", "OpenCost"];
    const valResources = ["DeepEval", "Jaeger", "Zipkin", "Guardrails AI", "Pydantic AI", "Instructor"];
    const qualResources = ["LangSmith", "Ragas", "AgentOps", "Confident AI", "TruLens"];
    const prodResources = ["OpenTelemetry", "Apache SkyWalking", "Langfuse", "Prometheus"];
    const riskResources = ["Rebuff", "LLMGuard", "TruLens"];
    const govResources = ["Detect-Secrets", "Microsoft Presidio", "Open Policy Agent"];
    // Tag Langfuse cost rows so they can be distinguished from execution rows
    const langfuseCostRows = costData
      .filter(r => r.resource_name === 'Langfuse')
      .map(r => ({ ...r, _dimension: 'cost' }));
    const langfuseExecRows = execData
      .filter(r => r.resource_name === 'Langfuse')
      .map(r => ({ ...r, _dimension: 'execution' }));
    allData = [
      ...costData.filter(r => costResources.includes(r.resource_name)),
      ...valData.filter(r => valResources.includes(r.resource_name)),
      ...qualData.filter(r => qualResources.includes(r.resource_name)),
      ...prodData.filter(r => prodResources.includes(r.resource_name)),
      ...langfuseCostRows,
      ...langfuseExecRows,
      ...execData.filter(r => ['Phoenix', 'Traceloop'].includes(r.resource_name)),
      ...riskData.filter(r => riskResources.includes(r.resource_name)),
      ...govData.filter(r => govResources.includes(r.resource_name))
    ];
    renderGrid();
  } catch (e) {
    document.getElementById('resources-grid').innerHTML = `
      <div class="empty-wrap" style="grid-column:1/-1">
        <div class="empty-icon">⚠️</div>
        <div class="empty-title">Could not load evaluations</div>
        <div class="empty-sub">${escHtml(e.message)}<br><br>Make sure the DPI-LS server is running on port 8000.</div>
        <button class="run-btn" onclick="loadData()" style="margin-top:16px">↺ Retry</button>
      </div>`;
  }
}

function renderGrid() {
const grouped = groupByResource(allData);

// Always render ALL 20 registered resources — even when the API has not
// returned telemetry for them yet (e.g. Governance before a live agent run).
// Union the canonical RESOURCE_META keys with whatever the API returned.
const allNames = Array.from(new Set([...Object.keys(RESOURCE_META), ...Object.keys(grouped)]));

// Sort by dpi_status priority then by name
const sortedNames = allNames.sort((a, b) => {
    const ma = RESOURCE_META[a]?.dpi_status || 'optional';
    const mb = RESOURCE_META[b]?.dpi_status || 'optional';
    const oa = STATUS_ORDER[ma] ?? 99;
    const ob = STATUS_ORDER[mb] ?? 99;
    if (oa !== ob) return oa - ob;
    return a.localeCompare(b);
  });

  // Stats
  const totalEvals = allData.length;
  const totalDetected = allData.filter(m => m.detected).length;
  const successCount = sortedNames.filter(n => resourceStatus(n, grouped[n] || []) === 'success').length;
  const failedCount  = sortedNames.filter(n => resourceStatus(n, grouped[n] || []) === 'failed').length;

  document.getElementById('count-all').textContent = sortedNames.length;
  document.getElementById('count-success').textContent = successCount;
  document.getElementById('count-failed').textContent = failedCount;
  document.getElementById('total-detected-pill').textContent = `${totalDetected} metrics detected`;
  document.getElementById('total-evals-pill').textContent = `${totalEvals} evaluations`;

  if (sortedNames.length === 0) {
    document.getElementById('resources-grid').innerHTML = `
      <div class="empty-wrap" style="grid-column:1/-1">
        <div class="empty-icon">🔬</div>
        <div class="empty-title">No evaluations run yet</div>
        <div class="empty-sub">Click "Run Evaluation" to execute the Technical Evaluation Workflow across all 20 resources.</div>
        <button class="run-btn" onclick="runEvaluation()" style="margin-top:16px">▶ Run Evaluation</button>
      </div>`;
    return;
  }

  const html = sortedNames.map(name => renderResourceCard(name, grouped[name])).join('');
  document.getElementById('resources-grid').innerHTML = html;
  applyFilter();
}

// Initial load + auto-refresh every 15s
loadUrls().then(() => {
  loadData();
  setInterval(loadData, 15000);
});

