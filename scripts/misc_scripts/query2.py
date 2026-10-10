from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from store.repo import latest_scores_for_all

engine = create_engine('sqlite:///dpi_ls.db')
SessionLocal = sessionmaker(bind=engine)
s = SessionLocal()

scores = latest_scores_for_all(s)
for agent, score in scores:
    if agent.name == "Chandra":
        print(f"Agent: {agent.id}, Score ID: {score.id}, Score: {score.score}, G: {score.metrics.get('G')}")
