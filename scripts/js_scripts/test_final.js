const fs = require('fs');
eval(fs.readFileSync('widget/dpi-ls.js', 'utf8'));

// Since it's not a module, the functions are global
let sub = {
  iterations_used: 0,
  attempts: undefined,
  total_attempts: undefined,
  trace_captured: "1",
  successful: undefined,
  successful_executions: 0,
  trace_status: "success"
};

let metrics = calculateExecutionMetrics(sub, {}, 0);
console.log("Total_Attempts:", metrics.Total_Attempts ? metrics.Total_Attempts.val : "Missing");
console.log("Successful_Attempts:", metrics.Successful_Attempts ? metrics.Successful_Attempts.val : "Missing");
console.log("Execution_Score:", metrics.Execution_Score ? metrics.Execution_Score.val : "Missing");
