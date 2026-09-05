import re

def safe_replace(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        c = f.read()

    # Just remove the elements from the lists
    c = c.replace('"DeepEval", "Jaeger", "Zipkin", "Guardrails AI", "Pydantic AI", "Instructor"', '"DeepEval", "Guardrails AI", "Pydantic AI", "Instructor"')
    
    # Remove from dicts and tuples by regex matching the whole line
    c = re.sub(r'^\s*"Jaeger":.*?\n', '', c, flags=re.MULTILINE)
    c = re.sub(r'^\s*"Zipkin":.*?\n', '', c, flags=re.MULTILINE)
    c = re.sub(r'^\s*\("Jaeger".*?\n', '', c, flags=re.MULTILINE)
    c = re.sub(r'^\s*\("Zipkin".*?\n', '', c, flags=re.MULTILINE)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(c)

safe_replace('dpi_ls/validation_resource_evaluation_service.py')
