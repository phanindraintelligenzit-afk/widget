import re

for filepath in ['.env', '.env.example', '.env.template']:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            c = f.read()
        
        c = re.sub(r'^.*JAEGER.*$\n', '', c, flags=re.MULTILINE|re.IGNORECASE)
        c = re.sub(r'^.*ZIPKIN.*$\n', '', c, flags=re.MULTILINE|re.IGNORECASE)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(c)
    except FileNotFoundError:
        pass
