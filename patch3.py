import re
with open('api/app.py', 'r', encoding='utf-8') as f:
    app = f.read()
app = re.sub(r'                      with SessionLocal\(\) as session:\n                  except Exception as e:', '                      pass\n                  except Exception as e:', app)
with open('api/app.py', 'w', encoding='utf-8') as f:
    f.write(app)
