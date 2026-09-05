with open('api/scoring.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if 'llmguard = {"Prompt Injection' in line: continue
    if 'rebuff = {"Attack Count' in line: continue
    if 'trulens = {"Hallucinations' in line: continue
    if 'prometheus = {"High CPU' in line: continue
    
    if 'elif src == "LLMGuard":' in line:
        skip = True
        continue
    if skip and 'elif src == "Falco":' in line:
        skip = False
    
    if skip: continue
    
    if 'elif src == "Prometheus":' in line:
        skip = True
        continue
    if skip and 'sub_metrics["R"].update({' in line:
        skip = False

    if skip: continue

    if '"LLMGuard": llmguard,' in line: continue
    if '"Rebuff": rebuff,' in line: continue
    if '"TruLens": trulens,' in line: continue
    if '"Prometheus": prometheus' in line: continue
    
    new_lines.append(line)

with open('api/scoring.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
