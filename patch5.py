with open('api/app.py', 'r', encoding='utf-8') as f:
    app = f.read()
app = app.replace('''    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }''', '')
with open('api/app.py', 'w', encoding='utf-8') as f:
    f.write(app)
