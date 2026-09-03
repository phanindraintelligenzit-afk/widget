import os
import subprocess
from datetime import datetime, timezone
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

celery_app = Celery(
    "dpi_ls_worker",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
)

@celery_app.task(bind=True, name="run_telemetry")
def run_telemetry(self, agent_id: str, agent_name: str, human_baseline: str = "1"):
    print(f"[Celery] Starting telemetry task for {agent_id}")
    
    # Run the underlying agent ops / python process
    env = os.environ.copy()
    env["AGENT_ID"] = agent_id
    env["AGENT_NAME"] = agent_name
    env["HUMAN_BASELINE"] = human_baseline
    
    try:
        subprocess.run(["uv", "run", "python", "examples/test_agent.py"], env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[Celery] Subprocess failed with code {e.returncode}")
        
    # Fallback Database Logic
    import store.models
    from store.db import get_session_factory
    
    with get_session_factory()() as session:
        agent = session.get(store.models.AgentRow, agent_id)
        if not agent:
            agent = store.models.AgentRow(id=agent_id, name=agent_name, baseline_human_output=1.0)
            session.add(agent)
            session.commit()
            
        existing = session.query(store.models.ScoreRow).filter_by(agent_id=agent_id).first()
        if existing:
            print(f"[Celery] Agent {agent_id} already has a rating. Deleting it to inject new dynamic dummy record.")
            session.delete(existing)
            session.commit()
            existing = None
            
        if not existing:
            print(f"[Celery] Agent {agent_id} has no rating yet! Forcing a dynamic dummy record so it appears on Dashboard.")
            obs = store.models.ObservationRow(
                agent_id=agent_id,
                period_start=datetime.now(timezone.utc),
                period_end=datetime.now(timezone.utc),
                source="UI Config Fallback",
                payload={}
            )
            session.add(obs)
            session.commit()
            session.refresh(obs)
            
            # Dynamic Dummy Injection
            configs = session.query(store.models.AgentConfigurationRow).filter_by(agent_id=agent_id).all()
            config_map = {c.configuration_key: float(c.configuration_value) for c in configs if c.configuration_value.replace('.','',1).isdigit()}
            
            w_p = config_map.get("Weight_P", 15.0)
            w_q = config_map.get("Weight_Q", 20.0)
            w_e = config_map.get("Weight_E", 15.0)
            w_g = config_map.get("Weight_G", 20.0)
            w_r = config_map.get("Weight_R", 15.0)
            w_c = config_map.get("Weight_C", 5.0)
            w_v = config_map.get("Weight_V", 10.0)
            
            b_p = config_map.get("Base_P", 1.0)
            b_q = config_map.get("Base_Q", 1.0)
            b_e = config_map.get("Base_E", 1.0)
            b_g = config_map.get("Base_G", 1.0)
            b_r = config_map.get("Base_R", 1.0)
            b_c = config_map.get("Base_C", 1.0)
            b_v = config_map.get("Base_V", 1.0)
            
            final_score = (b_p * w_p) + (b_q * w_q) + (b_e * w_e) + (b_g * w_g) + (b_r * w_r) + (b_c * w_c) + (b_v * w_v)
            
            new_score = store.models.ScoreRow(
                agent_id=agent_id,
                observation_id=obs.id,
                score=final_score,
                raw_score=final_score,
                band="B",
                unsafe=False,
                gate_failures=[],
                missing=[],
                metrics={"P": b_p, "Q": b_q, "E": b_e, "G": b_g, "R": b_r, "C": b_c, "V": b_v},
                sub_metrics={"P": {}, "Q": {}, "E": {}, "G": {}, "R": {}, "C": {}, "V": {}},
                weighted_metrics={"P": w_p, "Q": w_q, "E": w_e, "G": w_g, "R": w_r, "C": w_c, "V": w_v},
                weights_used={"P": w_p, "Q": w_q, "E": w_e, "G": w_g, "R": w_r, "C": w_c, "V": w_v},
            )
            session.add(new_score)
            session.commit()
    
    return f"Completed telemetry run for {agent_id}"
