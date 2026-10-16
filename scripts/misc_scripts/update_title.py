import os
import glob

widget_dir = "widget"
target_string = "DPI-LS (Digital Performance Index - Life Science)"
replacement_string = "Digital Performance Index"

html_files = glob.glob(os.path.join(widget_dir, "*.html"))
for file_path in html_files:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if target_string in content:
        new_content = content.replace(target_string, replacement_string)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated: {file_path}")
