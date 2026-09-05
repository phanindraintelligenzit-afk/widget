with open('dpi_ls/quality_resource_evaluation_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '"AgentOps": ["runtime_execution_history", "agent_behaviour", "consistency_measurement", "session_metrics", "stability_metrics"]\n        }',
    '"AgentOps": ["runtime_execution_history", "agent_behaviour", "consistency_measurement", "session_metrics", "stability_metrics"],\n            "DeepEval": ["answer_relevancy", "faithfulness", "hallucination", "correctness"]\n        }'
)

with open('dpi_ls/quality_resource_evaluation_service.py', 'w', encoding='utf-8') as f:
    f.write(content)
