from PIL import Image, ImageDraw, ImageFont

# Image dimensions based on PPTX picture: width=6858000, height=4754880
# In pixels (assuming 914400 EMU per inch and 96 DPI): 
# 6858000 / 914400 * 96 = 720
# 4754880 / 914400 * 96 = 499 (Let's use 1440x1000 for high resolution)
width, height = 1440, 1000
img = Image.new('RGB', (width, height), color=(30, 30, 30))
d = ImageDraw.Draw(img)

# Fallback font
try:
    font_large = ImageFont.truetype("arialbd.ttf", 40)
    font_med = ImageFont.truetype("arialbd.ttf", 30)
    font_small = ImageFont.truetype("arial.ttf", 24)
except:
    font_large = font_med = font_small = ImageFont.load_default()

# Header Dark Green
d.rectangle([0, 0, width, 120], fill=(0, 100, 50))
d.text((40, 30), "QUALITY (Q)", fill=(255, 255, 255), font=font_large)
d.text((40, 80), "Formula, Examples & Quality Rule", fill=(200, 255, 200), font=font_small)

# Formula Section
d.rectangle([40, 140, width-40, 300], outline=(100, 100, 100), width=2)
d.text((60, 160), "FORMULA", fill=(150, 150, 255), font=font_med)
d.text((60, 200), "Quality Score = Successful Quality Checks / Total Required Quality Checks", fill=(255, 255, 255), font=font_med)
d.text((60, 240), "Simple Meaning: Count how many Quality checks passed.", fill=(200, 200, 200), font=font_small)

# Left Panel (Green - Good Example)
d.rectangle([40, 320, width//2 - 20, 800], fill=(0, 60, 30), outline=(0, 150, 50), width=3)
d.text((60, 340), "GOOD EXAMPLE", fill=(100, 255, 100), font=font_med)
d.text((60, 400), "Required Quality Checks: 10\nPassed: 10\nQuality Score: 10 / 10 = 1.0", fill=(255, 255, 255), font=font_small)
d.text((60, 500), "Result:\n+ Accurate\n+ Relevant\n+ Faithful\n+ Grounded\n+ Consistent\n+ No Hallucination", fill=(200, 255, 200), font=font_small)
d.text((60, 720), "Final Quality Score: 1.0", fill=(255, 255, 255), font=font_med)

# Right Panel (Red - Bad Example)
d.rectangle([width//2 + 20, 320, width - 40, 800], fill=(60, 0, 0), outline=(200, 50, 50), width=3)
d.text((width//2 + 40, 340), "BAD EXAMPLE", fill=(255, 100, 100), font=font_med)
d.text((width//2 + 40, 400), "Required Quality Checks: 10\nPassed: 5\nQuality Score: 5 / 10 = 0.5", fill=(255, 255, 255), font=font_small)
d.text((width//2 + 40, 500), "Problems:\n- Hallucination\n- Wrong Context\n- Incorrect Facts\n- Poor Relevancy\n- Low Faithfulness\n- Weak Reasoning", fill=(255, 200, 200), font=font_small)
d.text((width//2 + 40, 720), "Final Quality Score: 0.5", fill=(255, 255, 255), font=font_med)

# Bottom Red Safety Rule
d.rectangle([40, 820, width - 40, 960], fill=(100, 0, 0))
d.text((60, 840), "BOTTOM RED SAFETY RULE", fill=(255, 100, 100), font=font_med)
d.text((60, 880), "If Quality Score drops below the configured threshold, Overall DPI-LS score is capped.\nExecution is flagged. Production deployment requires manual investigation.", fill=(255, 255, 255), font=font_small)

img.save('quality_example.png')
print("Image saved as quality_example.png")
