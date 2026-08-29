with open('widget/onboarding.html', 'r', encoding='utf-8') as f:
    content = f.read()

start_idx = content.find('        if (res.ok) {')
end_idx = content.find('  </script>\n  </main>')
if end_idx == -1:
    end_idx = content.find('  </script>\r\n  </main>')

if start_idx != -1 and end_idx != -1:
    # Walk backwards to find the `      });`
    close_idx = content.rfind('      });', 0, start_idx)
    if close_idx != -1:
        new_content = content[:close_idx + 9] + "\n" + content[end_idx:]
        with open('widget/onboarding.html', 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Patched via CRLF indices!")
else:
    print(f"Indices: {start_idx}, {end_idx}")
