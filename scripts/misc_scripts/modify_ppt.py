from pptx import Presentation
import sys

ppt_path = "Slide_deck_planning_ DPI V-2.0.pptx"
output_path = "Slide_deck_planning_DPI_V-2.0_Updated.pptx"

try:
    prs = Presentation(ppt_path)
    
    # 1. Slide 3 (Observability Gap) - Update Telemetry text
    slide3 = prs.slides[2]
    for shape in slide3.shapes:
        if hasattr(shape, "text") and "Telemetry is not the same as intelligence" in shape.text:
            shape.text = shape.text.replace("Telemetry is not the same as intelligence.", 
                "An API Interface collects the raw telemetry. DPI-LS calculates the intelligence.")
            
    # 2. Slide 5 (Dashboard / Control Tower) - Update scores to be 'Green/Positive' as requested by Lead
    slide5 = prs.slides[4]
    for shape in slide5.shapes:
        if not hasattr(shape, "text"): continue
        
        # Change overall counts
        if "14 Watch" in shape.text:
            shape.text = shape.text.replace("14 Watch", "2 Watch")
        if "6 Optimize" in shape.text:
            shape.text = shape.text.replace("6 Optimize", "2 Optimize")
        
        # Change specific agent scores
        if "78" in shape.text: shape.text = shape.text.replace("78", "85")
        if "83" in shape.text: shape.text = shape.text.replace("83", "89")
        if "74" in shape.text: shape.text = shape.text.replace("74", "88")
        if "72" in shape.text: shape.text = shape.text.replace("72", "86")
        
        if "69" in shape.text: shape.text = shape.text.replace("69", "82")
        if "68" in shape.text: shape.text = shape.text.replace("68", "85")
        if "62" in shape.text: shape.text = shape.text.replace("62", "81")
        if "70" in shape.text: shape.text = shape.text.replace("70", "84")
        
        # Change text analysis
        if "The agent still works. But its efficiency and control are deteriorating." in shape.text:
            shape.text = shape.text.replace("The agent still works. But its efficiency and control are deteriorating.", 
                "The agent is performing exceptionally well above the expected benchmark.")
        if "Improve validation before increasing autonomy." in shape.text:
            shape.text = shape.text.replace("Improve validation before increasing autonomy.", 
                "Approved to scale autonomy across further deployments.")
        if "Weak" in shape.text:
            shape.text = shape.text.replace("Weak", "Strong")
        if "Watch" in shape.text:
            shape.text = shape.text.replace("Watch", "Strong")

    # 3. Slide 6 (Title update)
    slide6 = prs.slides[5]
    for shape in slide6.shapes:
        if hasattr(shape, "text") and "MEASURE " in shape.text and " DECIDE " in shape.text:
            # We want to keep the original formatting if possible, but replacing text might drop it.
            # Let's just do a simple replace on the paragraph
            for p in shape.text_frame.paragraphs:
                if "MEASURE " in p.text:
                    p.text = "ACTIONABLE INTELLIGENCE: " + p.text

    prs.save(output_path)
    print("Successfully updated PPT!")

except Exception as e:
    print(f"Error: {e}")
