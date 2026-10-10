import re

def patch_dpi_js():
    with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
        content = f.read()
    
    pattern = re.compile(r'this\._data\s*=\s*\[\];\s*\}')
    
    injected_code = r"""this._data = [];
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
        // ------------------------------"""

    if not pattern.search(content):
        print("Could not find regex pattern in dpi-ls.js!")
        return
        
    content = pattern.sub(injected_code, content)

    # Replace data.map with renderData.map
    target_map = "${data.map(boardRowHtml).join(\"\""
    injected_map = "${renderData.map(boardRowHtml).join(\"\""
    
    content = content.replace(target_map, injected_map)

    with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
        f.write(content)
        print("Successfully injected filter logic into dpi-ls.js!")

if __name__ == '__main__':
    patch_dpi_js()
