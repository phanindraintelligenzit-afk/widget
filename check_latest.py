with open('store/repo.py', 'r', encoding='utf-8') as f:
    content = f.read()
    import re
    match = re.search(r'def latest_scores_for_all\(s: Session\) -> list\[tuple\[AgentRow, Optional\[ScoreRow\]\]\]:.*?return\s+\[.*?\]', content, re.DOTALL)
    if match:
        print(match.group(0))
