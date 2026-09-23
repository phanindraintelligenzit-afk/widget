from sqlalchemy.orm import Session
from api.dependencies import db_session
from store.repo import latest_scores_for_all

with next(db_session()) as s:
    res = latest_scores_for_all(s)
    for agent, score in res:
        print(f"Agent: {agent.name}, Score: {score}")
