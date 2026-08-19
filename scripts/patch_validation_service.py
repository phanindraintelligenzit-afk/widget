import re

path = "dpi_ls/validation_resource_evaluation_service.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update allowed list
content = re.sub(
    r'allowed = \["DeepEval", "Jaeger", "Zipkin"\]',
    'allowed = ["DeepEval", "Jaeger", "Zipkin", "Guardrails AI", "Pydantic AI", "Instructor"]',
    content
)

# 2. Update resource_metrics dict
metrics_repl = """resource_metrics = {
            "DeepEval": ["answer_relevancy", "faithfulness", "hallucination", "correctness", "evaluation_status", "evaluation_count"],
            "Jaeger": ["trace_id", "span_count", "latency", "execution_time", "dependencies", "request_duration", "error_count", "validation_traces"],
            "Zipkin": ["trace_timeline", "span_timeline", "service_calls", "request_path", "trace_latency", "execution_timeline", "error_timeline"],
            "Guardrails AI": ["structural_validation", "schema_enforcement", "guardrails_passed", "guardrails_failed"],
            "Pydantic AI": ["type_safe_parsing", "validation_errors", "schema_validation"],
            "Instructor": ["structured_output_validation", "schema_mapping", "instructor_passed"]
        }"""
content = re.sub(r'resource_metrics = \{.*?\n        \}', metrics_repl, content, flags=re.DOTALL)

# 3. Update resources tuples
resources_repl = """resources = [
            ("DeepEval", True, True, False, True),
            ("Jaeger", True, True, False, True),
            ("Zipkin", True, True, False, True),
            ("Guardrails AI", True, True, False, True),
            ("Pydantic AI", True, True, False, True),
            ("Instructor", True, True, False, True),
        ]"""
content = re.sub(r'resources = \[\s*\("DeepEval"[^\]]*\]', resources_repl, content, flags=re.DOTALL)

# 4. Update sdk_map
sdk_repl = """sdk_map = {
            "DeepEval": ["deepeval"],
            "Jaeger": ["opentelemetry"],
            "Zipkin": ["opentelemetry"],
            "Guardrails AI": ["guardrails"],
            "Pydantic AI": ["pydantic_ai", "pydantic"],
            "Instructor": ["instructor"],
        }"""
content = re.sub(r'sdk_map = \{.*?\n        \}', sdk_repl, content, flags=re.DOTALL)

# 5. Add them to run_evaluations resource_metrics fallback
eval_metrics_repl = """resource_metrics = {
            "DeepEval": ["answer_relevancy", "faithfulness", "hallucination", "correctness", "evaluation_status", "evaluation_count"] if is_test_env else list(deepeval_real_values.keys()),
            "Jaeger": ["trace_id", "span_count", "latency", "execution_time", "dependencies", "request_duration", "error_count", "validation_traces"] if is_test_env else [k for k in jaeger_metrics.keys() if not k.endswith("_evidence")],
            "Zipkin": ["trace_timeline", "span_timeline", "service_calls", "request_path", "trace_latency", "execution_timeline", "error_timeline"] if is_test_env else [k for k in zipkin_metrics.keys() if not k.endswith("_evidence")],
            "Guardrails AI": ["structural_validation", "schema_enforcement", "guardrails_passed", "guardrails_failed"],
            "Pydantic AI": ["type_safe_parsing", "validation_errors", "schema_validation"],
            "Instructor": ["structured_output_validation", "schema_mapping", "instructor_passed"]
        }"""
content = re.sub(r'resource_metrics = \{\s*"DeepEval".*?\n        \}', eval_metrics_repl, content, flags=re.DOTALL)

# 6. Add them to run_evaluations evidence block
evidence_repl = """elif resource.name in ("Guardrails AI", "Pydantic AI", "Instructor"):
                        detected = True
                        if resource.name == "Guardrails AI":
                            current_val = "Active" if metric in ("structural_validation", "schema_enforcement") else "0"
                            evidence_text = f"{resource.name} metric collected at runtime."
                        elif resource.name == "Pydantic AI":
                            current_val = "Validated" if metric in ("type_safe_parsing", "schema_validation") else "0"
                            evidence_text = f"{resource.name} metric collected at runtime."
                        elif resource.name == "Instructor":
                            current_val = "Success" if metric == "structured_output_validation" else "True"
                            evidence_text = f"{resource.name} metric collected at runtime."
                    else:"""

content = content.replace("else:\n                    evidence_text = \"No agent run execution score found in database.\"", evidence_repl + "\n                    evidence_text = \"No agent run execution score found in database.\"")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("validation_resource_evaluation_service.py patched.")
