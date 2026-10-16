with open('store/repo.py', 'r') as f:
    content = f.read()

content = content.replace(
    'CustomerRatingRow,',
    'CustomerRatingRow,\n    AgentWeightageRow,'
)

new_functions = '''
def get_agent_weightage(s: Session, agent_id: str) -> Optional[AgentWeightageRow]:
    return s.get(AgentWeightageRow, agent_id)

def upsert_agent_weightage(
    s: Session,
    agent_id: str,
    weight_p: float,
    weight_q: float,
    weight_e: float,
    weight_v: float,
    weight_r: float,
    weight_g: float,
    weight_c: float,
    total_weight: float
) -> AgentWeightageRow:
    row = s.get(AgentWeightageRow, agent_id)
    if row is None:
        row = AgentWeightageRow(
            agent_id=agent_id,
            weight_p=weight_p,
            weight_q=weight_q,
            weight_e=weight_e,
            weight_v=weight_v,
            weight_r=weight_r,
            weight_g=weight_g,
            weight_c=weight_c,
            total_weight=total_weight
        )
        s.add(row)
    else:
        row.weight_p = weight_p
        row.weight_q = weight_q
        row.weight_e = weight_e
        row.weight_v = weight_v
        row.weight_r = weight_r
        row.weight_g = weight_g
        row.weight_c = weight_c
        row.total_weight = total_weight
        row.updated_at = _utcnow()
    s.flush()
    return row
'''

with open('store/repo.py', 'w') as f:
    f.write(content + new_functions)
