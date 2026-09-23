from sqlalchemy.orm import Session
from api.dependencies import db_session
from sqlalchemy import select
from store.models import AgentRow

with next(db_session()) as s:
    res = s.execute(select(AgentRow)).scalars().all()
    for agent in res:
        print(f"Agent: {agent.name} (ID: {agent.id})")
