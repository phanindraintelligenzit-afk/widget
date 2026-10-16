import sys

def patch_config():
    with open('widget/agent-config.html', 'r', encoding='utf-8') as f:
        content = f.read()

    target = "Success! Generating real-time telemetry (this takes about 10-15 seconds)..."
    replacement = "Success! Generating real-time telemetry (this takes about 2-3 minutes)..."

    if target not in content:
        print("Failed to find target in agent-config.html")
        sys.exit(1)

    content = content.replace(target, replacement)

    with open('widget/agent-config.html', 'w', encoding='utf-8') as f:
        f.write(content)
        print("Successfully updated the time text in agent-config.html")

if __name__ == '__main__':
    patch_config()
