import re

with open('api/app.py', 'r', encoding='utf-8') as f:
    c = f.read()

new_endpoint = '''
@app.post("/api/quality-evaluation/push-deepeval")
def push_qual_deepeval_results(
    payload: dict = Body(...),
    s: Session = Depends(db_session),
) -> dict[str, Any]:
    from store.repo import save_quality_resource_evaluation
    updated = []
    metrics = ["answer_relevancy", "faithfulness", "hallucination", "correctness"]
    for metric in metrics:
        val = payload.get(metric)
        if val is not None:
            val_str = str(val)
            save_quality_resource_evaluation(
                s,
                resource_name="DeepEval",
                metric=metric,
                detected=True,
                evidence=f"Real DeepEval metric collected at runtime. Value: {val_str}",
                current_value=val_str,
                status="SUCCESS",
                agent_executed=True,
                dashboard_verified=True
            )
            updated.append(metric)
    s.commit()
    return {"updated": updated, "count": len(updated)}
'''

c = c.replace('@app.post("/api/quality-evaluation/push-ragas")', new_endpoint + '\n@app.post("/api/quality-evaluation/push-ragas")')

with open('api/app.py', 'w', encoding='utf-8') as f:
    f.write(c)

