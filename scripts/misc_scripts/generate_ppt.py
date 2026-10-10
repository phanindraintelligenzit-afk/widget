from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
import os

def create_ppt():
    prs = Presentation()
    
    # Slide 1: Title Slide
    slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(slide_layout)
    title = slide.shapes.title
    subtitle = slide.placeholders[1]
    title.text = "DPI Germany-India"
    subtitle.text = "The Complete AI Measurement Engine"
    
    # Slide 2: Introduction
    slide_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(slide_layout)
    title = slide.shapes.title
    title.text = "1. Introduction (The Elephant Concept)"
    body = slide.placeholders[1]
    tf = body.text_frame
    tf.text = "Moving beyond 'Can it do the work?' to 'Can we trust and scale it?'"
    p = tf.add_paragraph()
    p.text = "Like the Blind Men and the Elephant, measuring only one part of an AI misses the big picture."
    p = tf.add_paragraph()
    p.text = "DPI Germany-India sees the whole AI."
    
    # Speaker notes for Slide 2
    notes_slide = slide.notes_slide
    notes_slide.notes_text_frame.text = "Respected everyone, good afternoon. Today I am going to present DPI. First, I will explain what DPI is and why we built it. DPI stands for Digital Performance Index. It is a measurement engine that measures AI-agent performance.\n\nLike the story of the blind men and the elephant, if we only measure one thing, we miss the big picture. DPI helps us understand productivity, quality, risk, governance, validation, and cost as a whole before we trust and scale an AI agent."
    
    # Slide 3: Core Concept
    slide_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(slide_layout)
    title = slide.shapes.title
    title.text = "2. How DPI Works"
    body = slide.placeholders[1]
    tf = body.text_frame
    tf.text = "The Core Workflow:"
    p = tf.add_paragraph()
    p.text = "AI Agent -> Connect -> Measure -> Score -> Understand -> Improve -> Trust -> Scale"
    notes_slide = slide.notes_slide
    notes_slide.notes_text_frame.text = "How does DPI work? The core workflow is simple and continuous: AI Agent connects to the DPI Engine. We measure the data, calculate a score, and help you understand the performance. This allows you to improve the agent, build trust, and ultimately scale it."
    
    # Slide 4: Dimensions
    slide_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(slide_layout)
    title = slide.shapes.title
    title.text = "3. What Does DPI Measure? (The Paradox)"
    body = slide.placeholders[1]
    tf = body.text_frame
    tf.text = "Expanding the traditional Speed/Quality/Cost paradox into 7 Dimensions:"
    p = tf.add_paragraph()
    p.text = "1. Productivity (P)"
    p = tf.add_paragraph()
    p.text = "2. Quality (Q)"
    p = tf.add_paragraph()
    p.text = "3. Execution (E)"
    p = tf.add_paragraph()
    p.text = "4. Governance (G)"
    p = tf.add_paragraph()
    p.text = "5. Risk (R)"
    p = tf.add_paragraph()
    p.text = "6. Validation (V)"
    p = tf.add_paragraph()
    p.text = "7. Cost (C)"
    notes_slide = slide.notes_slide
    notes_slide.notes_text_frame.text = "Traditionally in engineering, there is a paradox: you have to choose between speed, quality, and cost. DPI expands this triangle into seven dimensions to measure the complete reality. We measure: Productivity, Quality, Execution, Governance, Risk, Validation, and Cost."
    
    # Slide 5: UI Flow Overview
    slide_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(slide_layout)
    title = slide.shapes.title
    title.text = "4. Application Demo (The Complete Flow)"
    body = slide.placeholders[1]
    tf = body.text_frame
    tf.text = "Complete UI Flow:"
    p = tf.add_paragraph()
    p.text = "Login -> Onboard Agent -> Configuration -> Dashboard -> Rating -> Profile -> Resources -> Sign Out"
    notes_slide = slide.notes_slide
    notes_slide.notes_text_frame.text = "Now, let me explain how the application works in practice. The complete flow is: Login, Onboard Agent, Configuration, Dashboard, Rating, Profile, Resources, and Sign Out."
    
    # Slide 6: Walkthrough
    slide_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(slide_layout)
    title = slide.shapes.title
    title.text = "5. Step-by-Step Walkthrough"
    body = slide.placeholders[1]
    tf = body.text_frame
    tf.text = "Login: Secure access to the 7 main sections."
    p = tf.add_paragraph()
    p.text = "Onboard: Enter details & Submit."
    p = tf.add_paragraph()
    p.text = "Configuration: Set the 7 weightages (Must equal 100%)."
    p = tf.add_paragraph()
    p.text = "Dashboard: See real-time scores and profiles."
    p = tf.add_paragraph()
    p.text = "Rating & Profile: Manual reviews and historical tracking."
    notes_slide = slide.notes_slide
    notes_slide.notes_text_frame.text = "Step 1, the user logs in. Step 2, they go to Onboard Agent and click Submit. Step 3, they are redirected to Configuration to update the 7 weightages, which must equal 100%. After saving, step 4, the calculated scores reflect on the Dashboard. Then the user can provide ratings which update the Profile section."

    # Slide 7: Resources
    slide_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(slide_layout)
    title = slide.shapes.title
    title.text = "6. Integrations & Resources"
    body = slide.placeholders[1]
    tf = body.text_frame
    tf.text = "18 Available Resources Integrated:"
    p = tf.add_paragraph()
    p.text = "Execution: Langfuse, OpenTelemetry, Jaeger"
    p = tf.add_paragraph()
    p.text = "Quality: Ragas, DeepEval, AgentOps"
    p = tf.add_paragraph()
    p.text = "Risk: Falco, Sentry, Prometheus"
    p = tf.add_paragraph()
    p.text = "Governance: OpenMetadata, OPA, Keycloak"
    p = tf.add_paragraph()
    p.text = "Cost: Langfuse, OpenCost, OpenLIT"
    p = tf.add_paragraph()
    p.text = "Productivity: Langfuse, Apache SkyWalking"
    p = tf.add_paragraph()
    p.text = "Validation: DeepEval, Guardrails AI, Pydantic AI"
    notes_slide = slide.notes_slide
    notes_slide.notes_text_frame.text = "The Resources section contains 18 available resources. DPI is designed to work with enterprise tools already generating data. We use Langfuse and OpenTelemetry for Execution, Ragas and DeepEval for Quality, Falco for Risk, and so on."
    
    # Slide 8: Value
    slide_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(slide_layout)
    title = slide.shapes.title
    title.text = "7. Value & Conclusion"
    body = slide.placeholders[1]
    tf = body.text_frame
    tf.text = "Measure -> Trust -> Scale"
    p = tf.add_paragraph()
    p.text = "Unified view for Business, Engineering, Risk, and Compliance."
    p = tf.add_paragraph()
    p.text = "Evidence-backed dimension scoring."
    notes_slide = slide.notes_slide
    notes_slide.notes_text_frame.text = "Finally, why should a customer trust our score? Because the DPI score is not a black-box number. We break the score down into seven dimensions and trace them back to exact evidence. The ultimate value is that it brings Business, Engineering, Risk, and Compliance into one unified view. Measure, Trust, Scale. Thank you."

    prs.save('D:\DPI-LS\widget\DPI_Germany_India_Presentation.pptx')

if __name__ == '__main__':
    create_ppt()
