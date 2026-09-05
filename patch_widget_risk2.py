import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

# Remove the metricsMap definitions for quality
c = re.sub(r'^\s*ground_truth_accuracy:\s*\{.*?"TruLens".*?\}\,?\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*trulens_faithfulness:\s*\{.*?"TruLens".*?\}\,?\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*hallucination_detection:\s*\{.*?"TruLens".*?\}\,?\n', '', c, flags=re.MULTILINE)

# Remove the resources extraction
c = re.sub(r'^\s*const llmguard = resources\["LLMGuard"\].*?$\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*const trulens = resources\["TruLens"\].*?$\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*const rebuff = resources\["Rebuff"\].*?$\n', '', c, flags=re.MULTILINE)

# Safely remove the if blocks by regex matching until the closing brace
c = re.sub(r'^\s*if \(Object\.keys\(llmguard\)\.length > 0\) \{[\s\S]*?^\s*\}\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*if \(Object\.keys\(trulens\)\.length > 0\) \{[\s\S]*?^\s*\}\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*if \(Object\.keys\(rebuff\)\.length > 0\) \{[\s\S]*?^\s*\}\n', '', c, flags=re.MULTILINE)

# Clean up arrays
c = c.replace('"TruLens"', '')
c = c.replace('"Rebuff", "LLMGuard", , ', '')
c = c.replace('"Rebuff", "LLMGuard", ', '')
c = c.replace('["Rebuff", "LLMGuard", , "Falco", "Sentry"]', '["Falco", "Sentry"]')
c = c.replace('["Rebuff", "LLMGuard", "Falco", "Sentry"]', '["Falco", "Sentry"]')
c = c.replace(', "TruLens", ', ', ')
c = c.replace(', , ', ', ')
c = c.replace('[, ', '[')
c = c.replace(', ]', ']')

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

