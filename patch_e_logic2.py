import re

with open('widget/dpi-ls.js', 'r', encoding='utf-8') as f:
    c = f.read()

old_logic = '''    let attempts = 0;
    if (!isNaN(Number(sub.iterations_used))) attempts = Number(sub.iterations_used);
    else if (!isNaN(Number(sub.attempts))) attempts = Number(sub.attempts);
    else if (!isNaN(Number(sub.total_attempts))) attempts = Number(sub.total_attempts);
    else if (!isNaN(Number(sub.trace_captured))) attempts = Number(sub.trace_captured);

    let successful = 0;
    if (!isNaN(Number(sub.successful))) successful = Number(sub.successful);
    else if (!isNaN(Number(sub.successful_executions))) successful = Number(sub.successful_executions);
    else if (sub.execution_status === 'success' || sub.execution_success === 1 || sub.execution_success === '1' || sub.execution_success === 'true' || sub.trace_status === 'success') successful = attempts; // Fallback to attempts if status is success and no raw count is provided'''

new_logic = '''    let attempts = 0;
    if (sub.trace_captured !== undefined && sub.trace_captured !== null && sub.trace_captured !== "Unavailable") attempts = Number(sub.trace_captured);
    else if (sub.iterations_used !== undefined && sub.iterations_used !== null && sub.iterations_used !== "Unavailable") attempts = Number(sub.iterations_used);
    else if (sub.attempts !== undefined && sub.attempts !== null && sub.attempts !== "Unavailable") attempts = Number(sub.attempts);
    else if (sub.total_attempts !== undefined && sub.total_attempts !== null && sub.total_attempts !== "Unavailable") attempts = Number(sub.total_attempts);

    let successful = 0;
    if (sub.trace_status === 'success' || sub.execution_success === 1 || sub.execution_success === '1' || sub.execution_success === 'true') successful = attempts;
    else if (sub.successful_executions !== undefined && sub.successful_executions !== null && sub.successful_executions !== "Unavailable") successful = Number(sub.successful_executions);
    else if (sub.successful !== undefined && sub.successful !== null && sub.successful !== "Unavailable") successful = Number(sub.successful);
    else if (sub.execution_status === 'success') successful = attempts;'''

c = c.replace(old_logic, new_logic)

with open('widget/dpi-ls.js', 'w', encoding='utf-8') as f:
    f.write(c)

