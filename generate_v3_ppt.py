from pptx import Presentation
from pptx.util import Pt
import os

prs = Presentation('Slide_deck_planning_DPI_V-2.0_Final.pptx')

# 1. Reorder slide 8 (index 7) to position 4 (index 3)
xml_slides = prs.slides._sldIdLst
slides = list(xml_slides)
slide_to_move = slides[7]
xml_slides.remove(slide_to_move)
xml_slides.insert(3, slide_to_move)

# 2. Modify Slide 2 (The AI Cost Paradox)
slide2 = prs.slides[1]
for shape in slide2.shapes:
    if hasattr(shape, "text"):
        if "73%" in shape.text:
            shape.text = shape.text.replace("73%", "40%+")
        if "Of organizations exceeded" in shape.text:
            shape.text = shape.text.replace("Of organizations exceeded their AI budgets in the past year", 
                                            "Increase in overall AI Spend. Must measure Efficiency / ROI at the Logical Unit via strict Comparison Strategy.")

# 3. Add New Slide for Pfizer ROI
blank_slide_layout = prs.slide_layouts[0]
slide_pfizer = prs.slides.add_slide(blank_slide_layout)
try:
    slide_pfizer.shapes.title.text = "Why Measuring Agent ROI is Critical"
except:
    pass

# We will just manually add a textbox for the content since placeholders might be weird
from pptx.util import Inches
txBox = slide_pfizer.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(5))
tf = txBox.text_frame
tf.text = "Why Measuring Agent ROI is Critical\n\n- Without measuring ROI at the logical unit, AI scales as a cost-center rather than a profit-driver.\n\n- Real-World Example (Pfizer): Top pharma companies like Pfizer measure the exact ROI of their AI systems by tracking time-saved in drug discovery data analysis and regulatory compliance checks against the actual token cost."

slides = list(xml_slides)
pfizer_slide_xml = slides[-1]
xml_slides.remove(pfizer_slide_xml)
xml_slides.insert(4, pfizer_slide_xml)

# 4. Add New Slide for Science -> Art -> Security
slide_sas = prs.slides.add_slide(blank_slide_layout)

txBox2 = slide_sas.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(5))
tf2 = txBox2.text_frame
tf2.text = "The Evolution of AI Measurement\n\n1. Science: The foundational engineering, LLMs, and compute.\n\n2. Art: Prompting, agentic behaviors, and workflows.\n\n3. Security: Governance, risk, and compliance.\n\n--> DPI (Digital Performance Index): The mathematical formula measuring and balancing Science, Art, and Security."

slides = list(xml_slides)
sas_slide_xml = slides[-1]
xml_slides.remove(sas_slide_xml)
xml_slides.insert(5, sas_slide_xml)

prs.save('Slide_deck_planning_DPI_V-3.0_Final.pptx')
print("Successfully created V-3.0")
