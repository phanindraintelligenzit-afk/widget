file_path = 'widget/agent-config.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Comment HTML
content = content.replace(
'''<div style="margin-top: 30px; background: #020617; border: 2px solid #334155; border-radius: 8px; padding: 20px; display: flex; justify-content: space-between; align-items: center;">
            <div style="font-family: 'Courier New', Courier, monospace;">
                <h4 style="margin: 0; color: #64748b; font-size: 13px; text-transform: uppercase;">Live DPI-LS Projection</h4>
                <div style="color: #38bdf8; font-size: 12px; margin-top: 5px;">(P * Q^1.5 * E) * (G^1.5 * R^2) * C * V</div>
            </div>
            <div style="font-size: 32px; font-weight: 800; color: #facc15;" id="live_dpi_score">0.00</div>
        </div>''',
'''<!-- <div style="margin-top: 30px; background: #020617; border: 2px solid #334155; border-radius: 8px; padding: 20px; display: flex; justify-content: space-between; align-items: center;">
            <div style="font-family: 'Courier New', Courier, monospace;">
                <h4 style="margin: 0; color: #64748b; font-size: 13px; text-transform: uppercase;">Live DPI-LS Projection</h4>
                <div style="color: #38bdf8; font-size: 12px; margin-top: 5px;">(P * Q^1.5 * E) * (G^1.5 * R^2) * C * V</div>
            </div>
            <div style="font-size: 32px; font-weight: 800; color: #facc15;" id="live_dpi_score">0.00</div>
        </div> -->'''
)

# Comment JS
content = content.replace(
'''        async function updateScorePreview() {''',
'''        async function updateScorePreview() {
            return; // Disabled per user request'''
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
