with open('api/schemas.py', 'a') as f:
    f.write('''
class AgentWeightageIn(BaseModel):
    weight_p: float
    weight_q: float
    weight_e: float
    weight_v: float
    weight_r: float
    weight_g: float
    weight_c: float

class AgentWeightageOut(AgentWeightageIn):
    agent_id: str
    total_weight: float
    updated_at: datetime
''')
