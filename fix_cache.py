import os

with open("widget/score.html", "r", encoding="utf-8") as f:
    html = f.read()

html = html.replace("fetch('/ratings?all=true');", "fetch('/ratings?all=true', { cache: 'no-store' });")

with open("widget/score.html", "w", encoding="utf-8") as f:
    f.write(html)
print("Added cache: 'no-store' to fetchAgents()")
