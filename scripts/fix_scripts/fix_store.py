import re

with open('store/repo.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace upsert_agent to also update name
new_func = '''def upsert_agent(
    s: Session,
    agent_id: str,
    agent_name: str,
    baseline: Optional[float] = None,
    owner_id: Optional[str] = None,
) -> AgentRow:
    import sqlalchemy.exc
    row = s.get(AgentRow, agent_id)
    if row is None:
        try:
            now = _utcnow()
            row = AgentRow(
                id=agent_id,
                name=agent_name,
                baseline_human_output=baseline or 1.0,
                owner_id=owner_id,
                first_seen=now,
                last_seen=now,
            )
            s.add(row)
            s.flush()
        except sqlalchemy.exc.IntegrityError:
            s.rollback()
            row = s.get(AgentRow, agent_id)
    if row is not None:
        row.name = agent_name
        if baseline is not None:
            row.baseline_human_output = baseline
        if owner_id is not None:
            row.owner_id = owner_id
        row.last_seen = _utcnow()
        s.flush()
    return row'''

content = re.sub(r'def upsert_agent\(.*?return row', new_func, content, flags=re.DOTALL)
with open('store/repo.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed store/repo.py")
