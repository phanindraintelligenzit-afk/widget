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
    pattern_body = r"(" + func_name + r"\s*\(.*?\)\s*(?:->\s*[^:]*)?:\n(?:\s*\"\"\"[^\"]*\"\"\"\n)?)"
    
    def replace_body(match):
        prefix = match.group(1)
        if "check_agent_ownership(agent_id, s, current_user)" in content[match.end():match.end()+200]:
            return prefix
        
        lines = content[match.end():match.end()+200].split('\n')
        indent = "    "
        for line in lines:
            if line.strip():
                indent = line[:len(line) - len(line.lstrip())]
                break
        return prefix + indent + "check_agent_ownership(agent_id, s, current_user)\n"

    content = re.sub(pattern_body, replace_body, content, flags=re.DOTALL)

app_path.write_text(content, encoding='utf-8')
print("Patched body!")
