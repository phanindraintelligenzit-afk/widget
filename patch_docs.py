for file in ['README.md', 'generate_clean_readme.py', 'generate_technical_readme.py', 'start.sh', 'docs/DPI-LS_BUSINESS_WORKFLOW_AND_MANUAL_TEST_GUIDE.md']:
    try:
        with open(file, 'r', encoding='utf-8') as f:
            c = f.read()
        
        c = c.replace('uv run uvicorn api.app:app --host 127.0.0.1 --port 8000', 'uv run uvicorn api.app:app --host 0.0.0.0 --port 8000')
        
        with open(file, 'w', encoding='utf-8') as f:
            f.write(c)
    except Exception as e:
        pass
