file_path = 'api/app.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re

old_preview = '''@app.post("/api/agents/{agent_id}/score/preview")
async def score_preview(agent_id: str, request: Request, s: Session = Depends(db_session), current_user: dict = Depends(get_current_user)):
    
    import engine.score
    import json
    
    body = await request.json()
    metrics = {
        "P": float(body.get("P", 1.0)),
        "Q": float(body.get("Q", 1.0)),
        "E": float(body.get("E", 1.0)),
        "G": float(body.get("G", 1.0)),
        "R": float(body.get("R", 1.0)),
        "V": float(body.get("V", 1.0)),
        "C": float(body.get("C", 1.0)),
    }
    
    # Optional dynamic weight distribution preview could be added here
    # For now, it uses defaults to show baseline calculation
    
    raw, _, _ = engine.score.composite(metrics)
    
    return {"preview_score": raw}'''

new_preview = '''@app.post("/api/agents/{agent_id}/score/preview")
async def score_preview(agent_id: str, request: Request, s: Session = Depends(db_session), current_user: dict = Depends(get_current_user)):
    
    import engine.score
    import json
    
    body = await request.json()
    metrics = {
        "P": float(body.get("P", 1.0)),
        "Q": float(body.get("Q", 1.0)),
        "E": float(body.get("E", 1.0)),
        "G": float(body.get("G", 1.0)),
        "R": float(body.get("R", 1.0)),
        "V": float(body.get("V", 1.0)),
        "C": float(body.get("C", 1.0)),
    }
    
    powers = {}
    multipliers = {}
    for m in ["P", "Q", "E", "G", "R", "C", "V"]:
        if f"Pow_{m}" in body:
            powers[m] = float(body[f"Pow_{m}"])
        if f"Mult_{m}" in body:
            multipliers[m] = float(body[f"Mult_{m}"])
            
    # Check DB if not provided in payload? Actually, payload comes straight from UI which has all current state.
    
    raw, _, _ = engine.score.composite(metrics, powers=powers, multipliers=multipliers)
    
    return {"preview_score": raw}'''

content = content.replace(old_preview, new_preview)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
