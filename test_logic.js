let sub = {
  iterations_used: 0,
  attempts: undefined,
  total_attempts: undefined,
  trace_captured: "1",
  successful: undefined,
  successful_executions: 0,
  trace_status: "success"
};

let attempts = 0;
if (!isNaN(Number(sub.iterations_used))) attempts = Number(sub.iterations_used);
else if (!isNaN(Number(sub.attempts))) attempts = Number(sub.attempts);
else if (!isNaN(Number(sub.total_attempts))) attempts = Number(sub.total_attempts);
else if (!isNaN(Number(sub.trace_captured))) attempts = Number(sub.trace_captured);

console.log("attempts:", attempts);

let successful = 0;
if (!isNaN(Number(sub.successful))) successful = Number(sub.successful);
else if (!isNaN(Number(sub.successful_executions))) successful = Number(sub.successful_executions);
else if (sub.execution_status === 'success' || sub.execution_success === 1 || sub.execution_success === '1' || sub.execution_success === 'true' || sub.trace_status === 'success') successful = attempts;

console.log("successful:", successful);
