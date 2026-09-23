import os
for root, dirs, files in os.walk('tests'):
    for file in files:
        if file.endswith('.py'):
            with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                if 'bob' in f.read():
                    print(file)
