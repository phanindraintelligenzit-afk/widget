import os

def generate_title_svg():
    os.makedirs('assets', exist_ok=True)
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" width="800" height="80">
  <text x="400" y="50" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="38" font-weight="bold">
    <tspan fill="#76b900">DPI-LS</tspan>
    <tspan fill="#24292e"> Digital FTE Performance Index for Life Sciences</tspan>
  </text>
</svg>
"""
    with open('assets/title.svg', 'w') as f:
        f.write(svg_content)

if __name__ == "__main__":
    generate_title_svg()
