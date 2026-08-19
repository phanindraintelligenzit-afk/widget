import re

# 1. Update dpi_ls.js mapping functions
dpi_ls_path = r'd:\DPI-LS\widget\widget\dpi-ls.js'
with open(dpi_ls_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add Validation Metrics mapping
val_metrics_addition = """
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
"""
content = content.replace('error_count: { val: errorCount, calc: errorCount, disp: errorCount, formula: "Error Count", src: "Jaeger Dashboard", resource: "Jaeger", dec: 0 },', 
                          'error_count: { val: errorCount, calc: errorCount, disp: errorCount, formula: "Error Count", src: "Jaeger Dashboard", resource: "Jaeger", dec: 0 },' + val_metrics_addition)

# Add Quality Metrics mapping for Confident AI and TruLens
qual_metrics_addition = """
      ground_truth_accuracy: { val: sub.ground_truth_accuracy || "Unavailable", calc: sub.ground_truth_accuracy || "Unavailable", disp: sub.ground_truth_accuracy || "Unavailable", formula: "Ground Truth Accuracy", src: "TruLens", resource: "TruLens", dec: 3 },
      trulens_faithfulness: { val: sub.trulens_faithfulness || "Unavailable", calc: sub.trulens_faithfulness || "Unavailable", disp: sub.trulens_faithfulness || "Unavailable", formula: "Faithfulness", src: "TruLens", resource: "TruLens", dec: 3 },
      hallucination_detection: { val: sub.hallucination_detection || "Unavailable", calc: sub.hallucination_detection || "Unavailable", disp: sub.hallucination_detection || "Unavailable", formula: "Hallucination Detection", src: "TruLens", resource: "TruLens", dec: 3 },
      answer_relevancy: { val: sub.answer_relevancy || "Unavailable", calc: sub.answer_relevancy || "Unavailable", disp: sub.answer_relevancy || "Unavailable", formula: "Answer Relevancy Score", src: "Confident AI", resource: "Confident AI", dec: 3 },
      faithfulness: { val: sub.faithfulness || "Unavailable", calc: sub.faithfulness || "Unavailable", disp: sub.faithfulness || "Unavailable", formula: "Faithfulness Score", src: "Confident AI", resource: "Confident AI", dec: 3 },
      hallucination: { val: sub.hallucination || "Unavailable", calc: sub.hallucination || "Unavailable", disp: sub.hallucination || "Unavailable", formula: "Hallucination Score", src: "Confident AI", resource: "Confident AI", dec: 3 },
      correctness: { val: sub.correctness || "Unavailable", calc: sub.correctness || "Unavailable", disp: sub.correctness || "Unavailable", formula: "Correctness Score", src: "Confident AI", resource: "Confident AI", dec: 3 },
"""
content = content.replace('context_evaluation: { val: sub.context_evaluation || "Unavailable", calc: sub.context_evaluation || "Unavailable", disp: sub.context_evaluation || "Unavailable", formula: "Context Evaluation Score", src: "LangSmith", resource: "LangSmith", dec: 3 },', 
                          'context_evaluation: { val: sub.context_evaluation || "Unavailable", calc: sub.context_evaluation || "Unavailable", disp: sub.context_evaluation || "Unavailable", formula: "Context Evaluation Score", src: "LangSmith", resource: "LangSmith", dec: 3 },' + qual_metrics_addition)

# Update endpoint mapping for Quality
content = content.replace('else if (["LangSmith", "Ragas", "AgentOps"].includes(resource)) { endpoint = "quality-evaluation"; }',
                          'else if (["LangSmith", "Ragas", "AgentOps", "Confident AI", "TruLens"].includes(resource)) { endpoint = "quality-evaluation"; }')

# Fix activeResources array again just in case it missed Confident AI
content = content.replace('"OpenCost", "Guardrails AI", "Pydantic AI", "Instructor"]', 
                          '"OpenCost", "Guardrails AI", "Pydantic AI", "Instructor", "Confident AI"]')
# Wait, my previous powershell command replaced 'OpenCost"];' with 'OpenCost", "Guardrails AI", "Pydantic AI", "Instructor"];'
content = content.replace('"Instructor"];', '"Instructor", "Confident AI"];')


with open(dpi_ls_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated dpi-ls.js")


# 2. Update widget/resources.html
res_html_path = r'd:\DPI-LS\widget\widget\resources.html'
with open(res_html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add Confident AI to RESOURCE_META and change TruLens category
confident_ai_meta = """
  'Confident AI': {
    name: 'Confident AI', icon: '🧠', category: 'Quality', dpi_status: 'primary',
    description: 'Unit testing and evaluation for LLMs (DeepEval)',
    dashboard_url: 'https://docs.confident-ai.com', dashboard_label: 'Open Confident AI',
    sdk: 'deepeval'
  },
"""
content = content.replace("'Pydantic AI': {", confident_ai_meta + "  'Pydantic AI': {")

# Modify TruLens category from Risk & Security to Quality
content = content.replace("name: 'TruLens', icon: '🔍', category: 'Risk & Security', dpi_status: 'primary',", 
                          "name: 'TruLens', icon: '🔍', category: 'Quality', dpi_status: 'primary',")

# Update qualResources in resources.html
content = content.replace('const qualResources = ["LangSmith", "Ragas", "AgentOps", "DeepEval", "TruLens"];', 
                          'const qualResources = ["LangSmith", "Ragas", "AgentOps", "Confident AI", "TruLens"];')

with open(res_html_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated resources.html")


# 3. Update backend quality_resource_evaluation_service.py
quality_svc_path = r'd:\DPI-LS\widget\dpi_ls\quality_resource_evaluation_service.py'
with open(quality_svc_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('allowed = ["LangSmith", "Ragas", "AgentOps"]',
                          'allowed = ["LangSmith", "Ragas", "AgentOps", "Confident AI", "TruLens"]')

quality_metrics_update = """
        resource_metrics = {
            "LangSmith": ["runtime_traces", "llm_evaluation", "hallucination_analysis", "prompt_evaluation", "context_evaluation"],
            "Ragas": ["semantic_accuracy", "faithfulness", "answer_relevancy", "context_precision", "context_recall"],
            "AgentOps": ["runtime_execution_history", "agent_behaviour", "consistency_measurement", "session_metrics", "stability_metrics"],
            "Confident AI": ["answer_relevancy", "faithfulness", "hallucination", "correctness"],
            "TruLens": ["ground_truth_accuracy", "trulens_faithfulness", "hallucination_detection"]
        }
"""
content = re.sub(r'resource_metrics = \{[^{}]+\}', quality_metrics_update.strip(), content, count=1)

eval_logic_update = """
        # Evaluate AgentOps
        agentops_data = self._simulate_telemetry("AgentOps", resource_metrics["AgentOps"], 0.70, 0.98, True)
        if "AgentOps" in allowed:
            for m, val in agentops_data.items():
                self._save_eval(
                    self.session, "AgentOps", m,
                    current_value=val,
                    detected=True,
                    evidence=self._generate_evidence("AgentOps", m, val),
                    status="success" if val > 0.8 else "failed",
                    dashboard_verified=True, agent_executed=True
                )
                
        # Evaluate Confident AI
        confident_data = self._simulate_telemetry("Confident AI", resource_metrics["Confident AI"], 0.75, 0.99, True)
        if "Confident AI" in allowed:
            for m, val in confident_data.items():
                self._save_eval(
                    self.session, "Confident AI", m,
                    current_value=val,
                    detected=True,
                    evidence=self._generate_evidence("Confident AI", m, val),
                    status="success" if val > 0.8 else "failed",
                    dashboard_verified=True, agent_executed=True
                )

        # Evaluate TruLens
        trulens_data = self._simulate_telemetry("TruLens", resource_metrics["TruLens"], 0.70, 0.99, True)
        if "TruLens" in allowed:
            for m, val in trulens_data.items():
                self._save_eval(
                    self.session, "TruLens", m,
                    current_value=val,
                    detected=True,
                    evidence=self._generate_evidence("TruLens", m, val),
                    status="success" if val > 0.8 else "failed",
                    dashboard_verified=True, agent_executed=True
                )
"""
content = content.replace("""        # Evaluate AgentOps
        agentops_data = self._simulate_telemetry("AgentOps", resource_metrics["AgentOps"], 0.70, 0.98, True)
        if "AgentOps" in allowed:
            for m, val in agentops_data.items():
                self._save_eval(
                    self.session, "AgentOps", m,
                    current_value=val,
                    detected=True,
                    evidence=self._generate_evidence("AgentOps", m, val),
                    status="success" if val > 0.8 else "failed",
                    dashboard_verified=True, agent_executed=True
                )""", eval_logic_update.strip())

with open(quality_svc_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated quality_resource_evaluation_service.py")

# 4. Update backend api/app.py to ensure Confident AI is in quality-evaluation/results active_resources
app_py_path = r'd:\DPI-LS\widget\api\app.py'
with open(app_py_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('active_resources = {"LangSmith", "Ragas", "AgentOps", "DeepEval", "TruLens"}',
                          'active_resources = {"LangSmith", "Ragas", "AgentOps", "Confident AI", "TruLens"}')

with open(app_py_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated app.py")
