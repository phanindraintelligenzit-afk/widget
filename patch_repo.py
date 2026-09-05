import re
from pathlib import Path

repo_path = Path('store/repo.py')
content = repo_path.read_text(encoding='utf-8')

old_code = '''        row = AgentRow(
            id=agent_id,
            name=agent_name,
            baseline_human_output=baseline if baseline is not None else 1.0,
        )'''
        
new_code = '''        row = AgentRow(
            id=agent_id,
            name=agent_name,
            baseline_human_output=baseline if baseline is not None else 1.0,
            owner_id=owner_id,
        )'''

content = content.replace(old_code, new_code)
repo_path.write_text(content, encoding='utf-8')
