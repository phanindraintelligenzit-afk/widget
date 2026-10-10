import sys

def patch_demo():
    with open('widget/demo.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Patch the Enter keypress logic
    t1 = """                    const matchedAgent = agents.find(a => 
                        (a.agent_id && a.agent_id.toLowerCase().includes(query)) || 
                        (a.agent_name && a.agent_name.toLowerCase().includes(query))
                    );"""
    
    r1 = """                    const normQuery = query.replace(/[-_]/g, ' ').replace(/\s+/g, ' ');
                    const matchedAgent = agents.find(a => {
                        const id = a.agent_id ? a.agent_id.toLowerCase().replace(/[-_]/g, ' ').replace(/\s+/g, ' ') : '';
                        const name = a.agent_name ? a.agent_name.toLowerCase().replace(/[-_]/g, ' ').replace(/\s+/g, ' ') : '';
                        return id.includes(normQuery) || name.includes(normQuery);
                    });"""

    # 2. Patch the Dropdown logic
    t2 = """                // Filter Agents
                const matchedAgents = agents.filter(a => (a.agent_id && a.agent_id.toLowerCase().includes(query)) || (a.agent_name && a.agent_name.toLowerCase().includes(query)));"""
    
    r2 = """                // Filter Agents
                const normQuery = query.replace(/[-_]/g, ' ').replace(/\s+/g, ' ');
                const matchedAgents = agents.filter(a => {
                    const id = a.agent_id ? a.agent_id.toLowerCase().replace(/[-_]/g, ' ').replace(/\s+/g, ' ') : '';
                    const name = a.agent_name ? a.agent_name.toLowerCase().replace(/[-_]/g, ' ').replace(/\s+/g, ' ') : '';
                    return id.includes(normQuery) || name.includes(normQuery);
                });"""

    if t1 not in content:
        print("Failed to find target 1 in demo.html")
        sys.exit(1)
        
    if t2 not in content:
        print("Failed to find target 2 in demo.html")
        sys.exit(1)

    content = content.replace(t1, r1)
    content = content.replace(t2, r2)

    with open('widget/demo.html', 'w', encoding='utf-8') as f:
        f.write(content)
        print("Successfully patched demo.html")

if __name__ == '__main__':
    patch_demo()
