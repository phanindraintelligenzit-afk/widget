import re
from pathlib import Path

app_path = Path('api/app.py')
content = app_path.read_text(encoding='utf-8')

endpoints_to_protect = [
    "def dashboard_risk",
    "def update_agent",
    "def get_onboarding",
    "def onboard_agent",
    "def create_kra",
    "def get_kras",
    "def update_agent_status",
    "def submit_manager_rating",
    "def list_manager_ratings",
    "def submit_customer_rating",
    "def list_customer_ratings",
    "def update_agent_config",
    "def run_telemetry",
    "def get_agent_configs",
    "def delete_agent",
    "def agent_score",
    "def agent_history",
    "def submit_sme_rating",
    "def dashboard_gov",
    "def execute_agent_eval",
    "def preview_score",
    "def test_connection"
]

for func_name in endpoints_to_protect:
    pattern = r"(" + func_name + r"\s*\(.*?\))(\s*(?:->\s*[^:]*)?:)"
    
    def replace_sig(match):
        sig = match.group(1)
        # only patch if agent_id is in signature
        if 'agent_id' not in sig:
            return match.group(0)
            
        if 'current_user: dict = Depends(get_current_user)' not in sig:
            # remove trailing paren
            sig = sig[:-1]
            if not sig.endswith(',') and not sig.endswith('('):
                sig += ', '
            sig += 'current_user: dict = Depends(get_current_user))'
        return sig + match.group(2)
        
    content = re.sub(pattern, replace_sig, content, flags=re.DOTALL)

app_path.write_text(content, encoding='utf-8')
print("Patched signatures properly!")
