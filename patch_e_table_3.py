with open("widget/dpi-ls.js", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
in_calc_exec = False
in_return_block = False

for line in lines:
    if "function calculateExecutionMetrics" in line:
        in_calc_exec = True
    
    if in_calc_exec and "return {" in line:
        in_return_block = True

    if in_calc_exec and in_return_block and "};" in line and "jaeger_trace:" not in line:
        # We hit the end of the return block for calculateExecutionMetrics
        # Let's inject our keys right before this closing brace
        injection = """        Total_Attempts:     { val: attempts, calc: attempts, disp: attempts, formula: "", src: "", resource: "Execution Engine", dec: 0 },
        Successful_Attempts:{ val: successful, calc: successful, disp: successful, formula: "", src: "", resource: "Execution Engine", dec: 0 },
        Execution_Score:    { val: calcEScore, calc: calcEScore, disp: calcEScore, formula: "", src: "", resource: "Execution Engine", dec: 3 },\n"""
        new_lines.append(injection)
        in_calc_exec = False
        in_return_block = False
        print("Injected execution metrics.")
        
    if "entries = entries.filter(([_, m]) => m.val !== \"Unavailable\");" in line:
        line = line.replace("entries = entries.filter(([_, m]) => m.val !== \"Unavailable\");", "entries = entries.filter(([key, m]) => m.val !== \"Unavailable\" && ![\"Total_Attempts\", \"Successful_Attempts\", \"Execution_Score\"].includes(key));")
        print("Replaced filter line.")

    new_lines.append(line)

with open("widget/dpi-ls.js", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
