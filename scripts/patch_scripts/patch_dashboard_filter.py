import re

def patch_demo_search():
    with open('widget/demo.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # Change redirect for Agent match (Enter key)
    # Old: window.location.href = '/widget/agent-profile.html?id=' + matchedAgent.agent_id;
    # New: window.location.href = '/widget/demo.html?agent=' + matchedAgent.agent_id;
    content = content.replace(
        "window.location.href = '/widget/agent-profile.html?id=' + matchedAgent.agent_id;",
        "window.location.href = '/widget/demo.html?agent=' + matchedAgent.agent_id;"
    )

    # Change redirect for Dropdown click
    # Old: window.location.href = `/widget/agent-profile.html?id=${a.agent_id}`;
    # New: window.location.href = `/widget/demo.html?agent=${a.agent_id}`;
    content = content.replace(
        "window.location.href = `/widget/agent-profile.html?id=${a.agent_id}`;",
        "window.location.href = `/widget/demo.html?agent=${a.agent_id}`;"
    )

    with open('widget/demo.html', 'w', encoding='utf-8') as f:
        f.write(content)

def patch_dpi_js():
    with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
        content = f.read()

    # Modify _render function to filter `data` based on `this.getAttribute("selected-agent")`
    
    # We will inject the filtering logic right after:
    # this._data = [];
    # }
    
    target_block = """        } else {
          this._data = [];
        }"""
        
    injected_code = """        } else {
          this._data = [];
        }
        
        // --- Added Filtering Logic ---
        let renderData = this._data || [];
        const selectedAgent = this.getAttribute("selected-agent");
        if (selectedAgent && renderData.length > 0) {
           const normFilter = selectedAgent.toLowerCase().replace(/[-_]/g, ' ').replace(/\\s+/g, ' ');
           renderData = renderData.filter(a => {
              const id = a.agent_id ? a.agent_id.toLowerCase().replace(/[-_]/g, ' ').replace(/\\s+/g, ' ') : '';
              const name = a.agent_name ? a.agent_name.toLowerCase().replace(/[-_]/g, ' ').replace(/\\s+/g, ' ') : '';
              return id.includes(normFilter) || name.includes(normFilter);
           });
        }
        // ------------------------------
"""
    if target_block in content:
        content = content.replace(target_block, injected_code)
    else:
        print("Could not find target block in dpi-ls.js!")

    # Replace data.map with renderData.map
    target_map = "${data.map(boardRowHtml).join(\"\")}"
    injected_map = "${renderData.map(boardRowHtml).join(\"\")}"
    
    if target_map in content:
        content = content.replace(target_map, injected_map)
    else:
        print("Could not find data.map target in dpi-ls.js!")

    with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    patch_demo_search()
    patch_dpi_js()
    print("Dashboard search and filter patched successfully!")
