import os
import glob

widget_dir = "widget"
html_files = glob.glob(os.path.join(widget_dir, "*.html"))

for file_path in html_files:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    changed = False
    
    # Update main header
    if ">Digital Performance Index<" in content:
        content = content.replace(">Digital Performance Index<", ">DPI (Digital Performance Index)<")
        changed = True
        
    # Update the formula label
    if "DPI-LS =" in content:
        content = content.replace("DPI-LS =", "DPI =")
        changed = True
        
    # Also in case score.html has DPI-LS in the table header
    if "DPI-LS" in content and file_path.endswith('score.html'):
        content = content.replace("DPI-LS", "DPI")
        changed = True

    if changed:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {file_path}")
