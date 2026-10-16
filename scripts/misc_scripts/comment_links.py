import os, glob
for file in glob.glob('d:/DPI-LS/widget/widget/*.html'):
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    modified = False
    if '<a href="/widget/score.html" class="nav-link">DPI-LS Score</a>' in content:
        content = content.replace('<a href="/widget/score.html" class="nav-link">DPI-LS Score</a>', '<!-- <a href="/widget/score.html" class="nav-link">DPI-LS Score</a> -->')
        modified = True
    if '<a href="/widget/score.html" class="nav-link active">DPI-LS Score</a>' in content:
        content = content.replace('<a href="/widget/score.html" class="nav-link active">DPI-LS Score</a>', '<!-- <a href="/widget/score.html" class="nav-link active">DPI-LS Score</a> -->')
        modified = True
        
    if modified:
        with open(file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Commented out DPI-LS Score link in {os.path.basename(file)}')
