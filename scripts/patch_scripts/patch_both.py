import os

# 1. Fix app.py
with open('api/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '    AgentStatusIn,\n)',
    '    AgentStatusIn,\n    AgentWeightageIn,\n    AgentWeightageOut\n)'
)

new_routes = '''
@app.get("/api/agents/{agent_id}/weightages", response_model=AgentWeightageOut)
def get_weightages(agent_id: str, s: Session = Depends(db_session)):
    row = store.repo.get_agent_weightage(s, agent_id)
    if not row:
        raise HTTPException(status_code=404, detail="Agent weightages not found")
    return AgentWeightageOut(
        agent_id=row.agent_id,
        weight_p=row.weight_p,
        weight_q=row.weight_q,
        weight_e=row.weight_e,
        weight_v=row.weight_v,
        weight_r=row.weight_r,
        weight_g=row.weight_g,
        weight_c=row.weight_c,
        total_weight=row.total_weight,
        updated_at=row.updated_at
    )

@app.put("/api/agents/{agent_id}/weightages", response_model=AgentWeightageOut)
def update_weightages(agent_id: str, body: AgentWeightageIn, s: Session = Depends(db_session)):
    total = sum([
        body.weight_p, body.weight_q, body.weight_e,
        body.weight_v, body.weight_r, body.weight_g, body.weight_c
    ])
    if abs(total - 100.0) > 0.01:
        raise HTTPException(status_code=400, detail="Total weight must equal exactly 100")
        
    row = store.repo.upsert_agent_weightage(
        s, agent_id,
        body.weight_p, body.weight_q, body.weight_e,
        body.weight_v, body.weight_r, body.weight_g, body.weight_c,
        total
    )
    s.commit()
    return AgentWeightageOut(
        agent_id=row.agent_id,
        weight_p=row.weight_p,
        weight_q=row.weight_q,
        weight_e=row.weight_e,
        weight_v=row.weight_v,
        weight_r=row.weight_r,
        weight_g=row.weight_g,
        weight_c=row.weight_c,
        total_weight=row.total_weight,
        updated_at=row.updated_at
    )
'''

if 'def get_weightages' not in content:
    with open('api/app.py', 'w', encoding='utf-8') as f:
        f.write(content + new_routes)


# 2. Patch scoring.py
with open('api/scoring.py', 'r', encoding='utf-8') as f:
    scoring_content = f.read()

helper = '''
def _get_custom_weightages(s: Session, agent_id: str):
    from store import repo
    row = repo.get_agent_weightage(s, agent_id)
    if row:
        return {
            "P": row.weight_p,
            "Q": row.weight_q,
            "E": row.weight_e,
            "V": row.weight_v,
            "R": row.weight_r,
            "G": row.weight_g,
            "C": row.weight_c
        }
    return None

def score_and_persist(
'''

if 'def _get_custom_weightages' not in scoring_content:
    scoring_content = scoring_content.replace('def score_and_persist(', helper)

    scoring_content = scoring_content.replace(
'''    powers, multipliers = _get_custom_formula_configs(s, obs.agent_id)
    rating = rate(
        metrics,
        weights=settings.weights,''',
'''    powers, multipliers = _get_custom_formula_configs(s, obs.agent_id)
    custom_weights = _get_custom_weightages(s, obs.agent_id)
    rating = rate(
        metrics,
        weights=custom_weights if custom_weights else settings.weights,'''
    )

    scoring_content = scoring_content.replace(
'''    powers, multipliers = _get_custom_formula_configs(s, agent_id)
    rating = rate(
        metrics,
        weights=settings.weights,''',
'''    powers, multipliers = _get_custom_formula_configs(s, agent_id)
    custom_weights = _get_custom_weightages(s, agent_id)
    rating = rate(
        metrics,
        weights=custom_weights if custom_weights else settings.weights,'''
    )

    with open('api/scoring.py', 'w', encoding='utf-8') as f:
        f.write(scoring_content)
