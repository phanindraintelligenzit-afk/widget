import re
from pathlib import Path

app_path = Path('api/app.py')
content = app_path.read_text(encoding='utf-8')

endpoints_to_protect = [
    "def get_onboarding",
    "def update_onboarding",
    "def get_kras",
    "def list_manager_ratings",
    "def list_customer_ratings",
    "def set_agent_config",
    "def run_telemetry_endpoint",
    "def get_agent_configs",
    "def agent_score",
    "def agent_history",
    "def governance_dashboard_data",
    "def enterprise_validation_agent_dashboard",
    "def enterprise_quality_agent_dashboard",
    "def enterprise_productivity_agent_dashboard",
    "async def execute_agent",
    "async def score_preview",
    "async def test_connection"
]

for ep in endpoints_to_protect:
    # Find the function definition
    match = re.search(ep + r'\s*\(.*?agent_id:\s*str.*?\):', content, flags=re.DOTALL)
    if not match:
        continue
    
    func_def = match.group(0)
    
    # If it already has current_user, skip
    if 'current_user' in func_def:
        continue
        
    # Inject current_user: dict = Depends(get_current_user)
    new_func_def = func_def.replace('):', ', current_user: dict = Depends(get_current_user)):')
    
    # Inject check_agent_ownership(agent_id, s, current_user) at the start of the body
    body_start_idx = match.end()
    
    # We need to find the correct indentation
    next_line = content[body_start_idx:].lstrip('\n')
    indent_match = re.match(r'([ \t]+)', next_line)
    indent = indent_match.group(1) if indent_match else '    '
    
    auth_call = f"\n{indent}check_agent_ownership(agent_id, s, current_user)"
    
    content = content[:match.start()] + new_func_def + auth_call + content[body_start_idx:]

# Fix create_agent
old_create = '''def create_agent(body: AgentCreate, s: Session = Depends(db_session)) -> AgentSummary:
    row = repo.upsert_agent(s, body.agent_id, body.agent_name, baseline=body.baseline_human_output)'''
new_create = '''def create_agent(body: AgentCreate, s: Session = Depends(db_session), current_user: dict = Depends(get_current_user)) -> AgentSummary:
    row = repo.upsert_agent(s, body.agent_id, body.agent_name, baseline=body.baseline_human_output, owner_id=current_user["username"])'''
content = content.replace(old_create, new_create)

app_path.write_text(content, encoding='utf-8')
