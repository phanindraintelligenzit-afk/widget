file_path = 'widget/agent-config.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_baseline = '''        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
            <div class="form-group"><label>Productivity (P)</label><input type="number" step="0.01" id="base_P" value="1.0" required></div>
            <div class="form-group"><label>Quality (Q)</label><input type="number" step="0.01" id="base_Q" value="0.99" required></div>
            <div class="form-group"><label>Efficiency (E)</label><input type="number" step="0.01" id="base_E" value="0.85" required></div>
            <div class="form-group"><label>Governance (G)</label><input type="number" step="0.01" id="base_G" value="1.0" required></div>
            <div class="form-group"><label>Risk (R)</label><input type="number" step="0.01" id="base_R" value="0.50" required></div>
            <div class="form-group"><label>Cost (C)</label><input type="number" step="0.01" id="base_C" value="0.70" required></div>
            <div class="form-group"><label>Validation (V)</label><input type="number" step="0.01" id="base_V" value="0.95" required></div>
        </div>'''

new_baseline = '''        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
            <div class="form-group" style="display: flex; gap: 10px; align-items: center;"><label style="width: 120px;">Productivity (P)</label><input type="number" step="0.01" id="base_P" value="1.0" required style="width: 70px;" title="Base"><span style="color:var(--muted)">x</span><input type="number" step="0.01" id="mult_P" value="1.0" required style="width: 70px;" title="Multiplier"><span style="color:var(--muted)">^</span><input type="number" step="0.01" id="pow_P" value="1.0" required style="width: 70px;" title="Power"></div>
            <div class="form-group" style="display: flex; gap: 10px; align-items: center;"><label style="width: 120px;">Quality (Q)</label><input type="number" step="0.01" id="base_Q" value="0.99" required style="width: 70px;" title="Base"><span style="color:var(--muted)">x</span><input type="number" step="0.01" id="mult_Q" value="1.0" required style="width: 70px;" title="Multiplier"><span style="color:var(--muted)">^</span><input type="number" step="0.01" id="pow_Q" value="1.5" required style="width: 70px;" title="Power"></div>
            <div class="form-group" style="display: flex; gap: 10px; align-items: center;"><label style="width: 120px;">Efficiency (E)</label><input type="number" step="0.01" id="base_E" value="0.85" required style="width: 70px;" title="Base"><span style="color:var(--muted)">x</span><input type="number" step="0.01" id="mult_E" value="1.0" required style="width: 70px;" title="Multiplier"><span style="color:var(--muted)">^</span><input type="number" step="0.01" id="pow_E" value="1.0" required style="width: 70px;" title="Power"></div>
            <div class="form-group" style="display: flex; gap: 10px; align-items: center;"><label style="width: 120px;">Governance (G)</label><input type="number" step="0.01" id="base_G" value="1.0" required style="width: 70px;" title="Base"><span style="color:var(--muted)">x</span><input type="number" step="0.01" id="mult_G" value="1.0" required style="width: 70px;" title="Multiplier"><span style="color:var(--muted)">^</span><input type="number" step="0.01" id="pow_G" value="1.5" required style="width: 70px;" title="Power"></div>
            <div class="form-group" style="display: flex; gap: 10px; align-items: center;"><label style="width: 120px;">Risk (R)</label><input type="number" step="0.01" id="base_R" value="0.50" required style="width: 70px;" title="Base"><span style="color:var(--muted)">x</span><input type="number" step="0.01" id="mult_R" value="1.0" required style="width: 70px;" title="Multiplier"><span style="color:var(--muted)">^</span><input type="number" step="0.01" id="pow_R" value="2.0" required style="width: 70px;" title="Power"></div>
            <div class="form-group" style="display: flex; gap: 10px; align-items: center;"><label style="width: 120px;">Cost (C)</label><input type="number" step="0.01" id="base_C" value="0.70" required style="width: 70px;" title="Base"><span style="color:var(--muted)">x</span><input type="number" step="0.01" id="mult_C" value="1.0" required style="width: 70px;" title="Multiplier"><span style="color:var(--muted)">^</span><input type="number" step="0.01" id="pow_C" value="1.0" required style="width: 70px;" title="Power"></div>
            <div class="form-group" style="display: flex; gap: 10px; align-items: center;"><label style="width: 120px;">Validation (V)</label><input type="number" step="0.01" id="base_V" value="0.95" required style="width: 70px;" title="Base"><span style="color:var(--muted)">x</span><input type="number" step="0.01" id="mult_V" value="1.0" required style="width: 70px;" title="Multiplier"><span style="color:var(--muted)">^</span><input type="number" step="0.01" id="pow_V" value="1.0" required style="width: 70px;" title="Power"></div>
        </div>'''

content = content.replace(old_baseline, new_baseline)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
