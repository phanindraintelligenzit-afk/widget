import os
import glob

old_search_logic = """        inp.addEventListener('input', async (e) => {
            const query = e.target.value.trim().toLowerCase();
            if (!query) {
                dropdown.style.display = 'none';
                return;
            }

            try {
                // Fetch live agents
                const res = await fetch('/ratings');
                let agents = [];
                if (res.ok) {
                    agents = await res.json();
                }"""

new_search_logic = """        let cachedAgents = null;
        let isFetching = false;
        
        inp.addEventListener('input', async (e) => {
            const query = e.target.value.trim().toLowerCase();
            if (!query) {
                dropdown.style.display = 'none';
                return;
            }

            try {
                // Fetch live agents only once to prevent async race condition during fast typing
                if (!cachedAgents && !isFetching) {
                    isFetching = true;
                    const res = await fetch('/ratings');
                    if (res.ok) cachedAgents = await res.json();
                    isFetching = false;
                }
                const agents = cachedAgents || [];"""

for filepath in glob.glob("widget/*.html"):
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()
    
    if old_search_logic in html:
        html = html.replace(old_search_logic, new_search_logic)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Patched {filepath} successfully.")
    else:
        print(f"Already patched or missing string in {filepath}")
