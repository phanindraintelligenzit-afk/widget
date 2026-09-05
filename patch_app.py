import re

with open('api/app.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = re.sub(r'''        # --- Apply Manager Ratings dynamically ---
        manager_ratings = repo.get_manager_ratings\(s, agent\.id\)
        if manager_ratings:
            latest_rating = manager_ratings\[0\]\.rating
            multiplier = latest_rating / 5\.0
            if "G" in m_dict: m_dict\["G"\] \*= multiplier
            if "E" in m_dict: m_dict\["E"\] \*= multiplier
            live_sub\["Manager Rating"\] = f"\{latest_rating\} / 5"''', '', c)

with open('api/app.py', 'w', encoding='utf-8') as f:
    f.write(c)
