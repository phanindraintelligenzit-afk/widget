from sqlalchemy.orm import Session
from api.dependencies import get_db
from store.repo import latest_scores_for_all

with next(get_db()) as s:
    res = latest_scores_for_all(s)
    for agent, score in res:
        print(f"Agent: {agent.name}, Score: {score}")
