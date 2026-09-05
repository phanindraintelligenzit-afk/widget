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
if (sub.trace_captured !== undefined && sub.trace_captured !== null && sub.trace_captured !== "Unavailable") attempts = Number(sub.trace_captured);
else if (sub.iterations_used !== undefined && sub.iterations_used !== null && sub.iterations_used !== "Unavailable") attempts = Number(sub.iterations_used);

let successful = 0;
if (sub.trace_status === 'success' || sub.execution_success === 1 || sub.execution_success === '1' || sub.execution_success === 'true') successful = attempts;

console.log("attempts:", attempts);
console.log("successful:", successful);
