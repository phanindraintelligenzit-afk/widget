import os
import re

files_to_update = [
    'widget/demo.html',
    'widget/resources.html',
    'widget/score.html',
    'widget/agent-profile.html',
    'widget/agent-config.html',
    'widget/onboarding.html'
]

# We need to inject the "Platform Sections" into the search logic.
# Let's find where we define `const metrics` and replace the logic from there down to `dropdown.style.display = 'flex';`

SEARCH_REPLACE_LOGIC = """                // Hardcode sections and metrics
                const metrics = ['Risk', 'Productivity', 'Quality', 'Efficiency', 'Governance', 'Cost', 'Validation'];
                const sections = [
                    {name: 'Dashboard', url: '/widget/demo.html'},
                    {name: 'Onboard Agent', url: '/widget/onboarding.html'},
                    {name: 'Configuration', url: '/widget/agent-config.html'},
                    {name: 'Rating (Manager Review)', url: '/widget/score.html'},
                    {name: 'Profile', url: '/widget/agent-profile.html'},
                    {name: 'Resources', url: '/widget/resources.html'}
                ];

                dropdown.innerHTML = '';
                let hasResults = false;

                // Filter Sections
                const matchedSections = sections.filter(s => s.name.toLowerCase().includes(query) || s.url.toLowerCase().includes(query));
                if (matchedSections.length > 0) {
                    const groupTitle = document.createElement('div');
                    groupTitle.style.padding = '8px 12px';
                    groupTitle.style.fontSize = '11px';
                    groupTitle.style.color = '#94a3b8';
                    groupTitle.style.fontWeight = 'bold';
                    groupTitle.style.textTransform = 'uppercase';
                    groupTitle.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                    groupTitle.textContent = 'Platform Sections';
                    dropdown.appendChild(groupTitle);

                    matchedSections.forEach(s => {
                        hasResults = true;
                        const item = document.createElement('div');
                        item.style.padding = '10px 12px';
                        item.style.cursor = 'pointer';
                        item.style.fontSize = '13px';
                        item.style.color = '#a78bfa';
                        item.style.transition = 'background 0.2s';
                        item.innerHTML = '&#128270; Navigate to: ' + s.name;
                        item.onmouseover = () => item.style.background = 'rgba(255,255,255,0.1)';
                        item.onmouseout = () => item.style.background = 'transparent';
                        item.onclick = () => {
                            window.location.href = s.url;
                        };
                        dropdown.appendChild(item);
                    });
                }

                // Filter Agents
                const matchedAgents = agents.filter(a => (a.agent_id && a.agent_id.toLowerCase().includes(query)) || (a.agent_name && a.agent_name.toLowerCase().includes(query)));
                const uniqueAgents = [];
                const seen = new Set();
                for(let a of matchedAgents) {
                    if(!seen.has(a.agent_id)) {
                        seen.add(a.agent_id);
                        uniqueAgents.push(a);
                    }
                }

                if (uniqueAgents.length > 0) {
                    const groupTitle = document.createElement('div');
                    groupTitle.style.padding = '8px 12px';
                    groupTitle.style.fontSize = '11px';
                    groupTitle.style.color = '#94a3b8';
                    groupTitle.style.fontWeight = 'bold';
                    groupTitle.style.textTransform = 'uppercase';
                    groupTitle.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                    groupTitle.style.marginTop = hasResults ? '5px' : '0';
                    groupTitle.textContent = 'Agents';
                    dropdown.appendChild(groupTitle);

                    uniqueAgents.forEach(a => {
                        hasResults = true;
                        const item = document.createElement('div');
                        item.style.padding = '10px 12px';
                        item.style.cursor = 'pointer';
                        item.style.fontSize = '13px';
                        item.style.color = '#38bdf8';
                        item.style.transition = 'background 0.2s';
                        item.innerHTML = '&#128100; ' + a.agent_id;
                        item.onmouseover = () => item.style.background = 'rgba(255,255,255,0.1)';
                        item.onmouseout = () => item.style.background = 'transparent';
                        item.onclick = () => {
                            window.location.href = `/widget/agent-profile.html?id=${a.agent_id}`;
                        };
                        dropdown.appendChild(item);
                    });
                }

                // Filter Metrics
                const matchedMetrics = metrics.filter(m => m.toLowerCase().includes(query));
                if (matchedMetrics.length > 0) {
                    const groupTitle = document.createElement('div');
                    groupTitle.style.padding = '8px 12px';
                    groupTitle.style.fontSize = '11px';
                    groupTitle.style.color = '#94a3b8';
                    groupTitle.style.fontWeight = 'bold';
                    groupTitle.style.textTransform = 'uppercase';
                    groupTitle.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                    groupTitle.style.marginTop = hasResults ? '5px' : '0';
                    groupTitle.textContent = 'Metrics';
                    dropdown.appendChild(groupTitle);

                    matchedMetrics.forEach(m => {
                        hasResults = true;
                        const item = document.createElement('div');
                        item.style.padding = '10px 12px';
                        item.style.cursor = 'pointer';
                        item.style.fontSize = '13px';
                        item.style.color = '#facc15';
                        item.style.transition = 'background 0.2s';
                        item.innerHTML = '&#128200; ' + m + ' Score';
                        item.onmouseover = () => item.style.background = 'rgba(255,255,255,0.1)';
                        item.onmouseout = () => item.style.background = 'transparent';
                        item.onclick = () => {
                            window.location.href = `/widget/demo.html?filter=${encodeURIComponent(m.toLowerCase())}`;
                        };
                        dropdown.appendChild(item);
                    });
                }

                if (!hasResults) {
                    const noRes = document.createElement('div');
                    noRes.style.padding = '10px 12px';
                    noRes.style.fontSize = '13px';
                    noRes.style.color = '#94a3b8';
                    noRes.textContent = 'No matches found';
                    dropdown.appendChild(noRes);
                }

                dropdown.style.display = 'flex';"""

for file_path in files_to_update:
    if not os.path.exists(file_path): continue
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We will replace from "// Hardcode metrics" down to "dropdown.style.display = 'flex';"
    pattern = re.compile(r'// Hardcode metrics.*?dropdown\.style\.display = \'flex\';', re.DOTALL)
    
    if pattern.search(content):
        content = pattern.sub(SEARCH_REPLACE_LOGIC.strip(), content)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            print(f"Updated Search logic in {file_path}")

print("Search logic upgraded!")
