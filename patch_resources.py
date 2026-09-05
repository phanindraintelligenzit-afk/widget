with open('widget/resources.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("url: 'http://localhost:", "url: 'http://' + window.location.hostname + ':")
content = content.replace("dashboard_url: 'http://localhost:", "dashboard_url: 'http://' + window.location.hostname + ':")

with open('widget/resources.html', 'w', encoding='utf-8') as f:
    f.write(content)
