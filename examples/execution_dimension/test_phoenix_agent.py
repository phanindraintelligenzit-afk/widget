"""
AWS Unified Agent
=================
Single-agent, self-healing AWS automation pipeline.

Combines the previously separate Generator, Executor, and Orchestrator
agents into one LangGraph state machine with a single shared AgentState.

Flow per iteration:
    read_existing -> read_reference -> analyze -> [hitl?] -> generate
        -> write_files -> scan_folder -> plan -> execute -> report -> route

route:
    - success             -> END
    - failed (retry left) -> back to read_existing (next iteration, with feedback)
    - failed (exhausted)  -> END
    - needs_clarification -> END (interrupt, resume with answers)
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import secrets
import shutil
import signal
import subprocess
import sys
import uuid
from itertools import zip_longest
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from dotenv import load_dotenv
from langchain_aws import ChatBedrockConverse
from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt
from langchain_core.tools import tool
from pydantic import BaseModel, Field

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("ExecutionAgents")

MAX_ITERATIONS = 5
DEFAULT_COMMAND_TIMEOUT = 300  # seconds


# ── Checkpointer ──────────────────────────────────────────────────────────────

def _build_checkpointer() -> Any:
    """Return a checkpointer using a three-tier fallback strategy.

    Tier 1: Postgres  (production)
    Tier 2: SQLite    (local disk, 'database/' folder)
    Tier 3: MemorySaver (in-process fallback)
    """
    # ── Tier 1: Postgres ──────────────────────────────────────────────────────
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg_pool import ConnectionPool
        import psycopg  # noqa: PLC0415 – optional heavy dep, intentionally deferred

        conn_string = os.getenv("POSTGRES_URL", "")
        if conn_string:
            if conn_string.startswith("postgresql+psycopg://"):
                conn_string = conn_string.replace("postgresql+psycopg://", "postgresql://", 1)
            with psycopg.connect(conn_string, autocommit=True) as conn:
                PostgresSaver(conn).setup()
            pool = ConnectionPool(conn_string, max_size=10)
            checkpointer = PostgresSaver(pool)
            logger.info("checkpointer.postgres_setup_success")
            return checkpointer
        logger.warning("checkpointer.postgres_url_missing")
    except ImportError:
        logger.warning("checkpointer.postgres_unavailable")
    except Exception as exc:
        logger.warning("checkpointer.postgres_setup_failed", exc_info=exc)

    # ── Tier 2: SQLite ────────────────────────────────────────────────────────
    try:
        import sqlite3  # noqa: PLC0415
        from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: PLC0415

        db_dir = Path("database")
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "checkpoints.sqlite"
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        checkpointer.setup()
        logger.info("checkpointer.sqlite_setup_success at %s", db_path)
        return checkpointer
    except ImportError:
        logger.warning("checkpointer.sqlite_unavailable")
    except Exception as exc:
        logger.warning("checkpointer.sqlite_setup_failed", exc_info=exc)

    # ── Tier 3: In-memory ─────────────────────────────────────────────────────
    logger.warning("checkpointer.fallback_to_memory_saver")
    return MemorySaver()


# ── Pydantic models ───────────────────────────────────────────────────────────

class ActionAnalysis(BaseModel):
    needs_clarification: bool = Field(
        description="True ONLY when critical information is missing"
    )
    questions: List[str] = Field(default_factory=list)
    recommended_approach: str = Field(description="'python' | 'terraform' | 'both'")
    reasoning: str = Field(description="Brief justification")


class GeneratedFile(BaseModel):
    filename: str
    content: str
    file_type: str
    description: str


class ExecutableStep(BaseModel):
    description: str
    command: str


class CodeGenerationResult(BaseModel):
    files: List[GeneratedFile]
    executableSteps: List[ExecutableStep]
    summary: str


class ExecutionCommand(BaseModel):
    command: str = Field(description="Shell command to execute")
    description: str = Field(description="What this command does")
    working_dir: str = Field(
        default=".",
        description="Working directory relative to execute_folder ('.' = root)",
    )
    order: int = Field(description="Execution order (1 = first)")


class ExecutionPlan(BaseModel):
    execution_type: str = Field(description="'python' | 'terraform' | 'shell' | 'mixed'")
    commands: List[ExecutionCommand] = Field(description="Ordered list of commands to run")
    reasoning: str = Field(description="Brief explanation of the execution strategy")


class ExecutionResult(BaseModel):
    command: str
    description: str
    working_dir: str
    stdout: str
    stderr: str
    return_code: int
    success: bool
    timed_out: bool = False
    timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT


class IterationRecord(BaseModel):
    iteration: int
    generator_status: str
    executor_status: str
    executor_success: bool
    feedback_used: Optional[str] = None
    sandbox_path: Optional[str] = None


class AgentState(TypedDict):
    # shared / control
    action: Dict[str, Any]
    reference_folder: str
    command_timeout: int
    max_iterations: int
    iteration: int
    records: List[Dict]
    feedback_summary: str

    # generator-related
    analysis: Optional[Dict]
    clarification: Optional[Dict]
    generated_files: List[Dict]
    executable_steps: List[Dict]
    sandbox_path: str
    existing_files: List[Dict]
    reference_files: List[Dict]
    input_sandbox_path: str
    generator_summary: str

    # executor-related
    folder_contents: Optional[str]
    execution_plan: Optional[Dict]
    execution_results: List[Dict]
    success: bool
    executor_summary: str

    # final
    final_status: str
    final_summary: str


class PipelineResponse(BaseModel):
    statusCode: int
    status: str = Field(description="'success' | 'failed' | 'error' | 'needs_clarification'")
    exception: Optional[str] = None
    thread_id: str
    sandbox_path: Optional[str] = None
    iterations_used: int = 0
    iterations: List[IterationRecord] = Field(default_factory=list)
    execution_results: Optional[List[ExecutionResult]] = None
    summary: Optional[str] = None
    questions: Optional[List[str]] = None

class CommandFailedError(Exception):
    def __init__(self, rc: int, stdout: str, stderr: str):
        super().__init__(f"Command failed with rc={rc}\n{stderr}")
        self.rc = rc
        self.stdout = stdout
        self.stderr = stderr

# ── LangChain Tools ───────────────────────────────────────────────────────────

@tool
def execute_shell_command(command: str, cwd: str, timeout: int) -> Dict[str, Any]:
    """Execute a shell command in a specific directory with a timeout."""
    proc_env = os.environ.copy()
    proc_env.setdefault("NO_COLOR", "1")
    proc_env.setdefault("TF_IN_AUTOMATION", "1")
    proc_env.setdefault("PYTHONIOENCODING", "utf-8")

    proc = subprocess.Popen(
        command,
        shell=True,
        cwd=cwd,
        env=proc_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    try:
        stdout_data, stderr_data = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                check=False,
            )
        else:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                proc.kill()
        try:
            stdout_data, stderr_data = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            stdout_data, stderr_data = "", ""
        raise TimeoutError(stderr_data or "Command timed out") from exc

    if proc.returncode != 0:
        raise CommandFailedError(rc=proc.returncode, stdout=stdout_data or "", stderr=stderr_data or "")

    return {
        "stdout": stdout_data or "",
        "stderr": stderr_data or "",
        "return_code": proc.returncode,
    }

# ── Unified Agent ─────────────────────────────────────────────────────────────

class ExecutionAgents:

    def __init__(self, max_iterations: int = MAX_ITERATIONS) -> None:
        self.max_iterations = max_iterations
        logger.info("Initialising ExecutionAgents (max_iterations=%d)", max_iterations)
        try:
            model_name = os.getenv("MODEL_NAME")
            if not model_name:
                raise ValueError(
                    "MODEL_NAME environment variable is not set. "
                    "Add MODEL_NAME=<bedrock-model-id> to your .env file."
                )
            self.Llm = ChatBedrockConverse(model_id=model_name)
            self.Checkpointer = _build_checkpointer()
            self.Graph = self._build_graph()
            logger.info("ExecutionAgents initialised successfully")
        except Exception as exc:
            logger.exception("Failed to initialise ExecutionAgents: %s", exc)
            raise

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _banner(text: str, char: str = "=", width: int = 78) -> None:
        logger.info(char * width)
        logger.info(text)
        logger.info(char * width)

    @staticmethod
    def _cleanup_sandbox(sandbox_path: Optional[str]) -> None:
        if sandbox_path and Path(sandbox_path).exists():
            try:
                shutil.rmtree(sandbox_path)
                logger.info("Cleaned up sandbox: %s", sandbox_path)
            except Exception as exc:
                logger.warning("Failed to clean up sandbox %s: %s", sandbox_path, exc)

    def _read_files_from_folder(self, folder_path: str, purpose: str = "files") -> List[Dict]:
        if not folder_path:
            return []

        path = Path(folder_path)
        if not path.exists() or not path.is_dir():
            logger.warning("%s folder '%s' does not exist", purpose, folder_path)
            return []

        ignore_dirs = {".terraform", ".git", "__pycache__"}
        allowed_extensions = {".tf", ".py", ".json", ".yaml", ".yml", ".md", ".sh"}
        skip_names = {"terraform.tfstate", "terraform.tfstate.backup", ".terraform.lock.hcl"}

        files: List[Dict] = []
        for file_path in sorted(path.rglob("*")):
            if not file_path.is_file():
                continue
            if any(part in ignore_dirs for part in file_path.parts):
                continue
            if file_path.name in skip_names:
                continue
            if (
                file_path.suffix not in allowed_extensions
                and not file_path.name.endswith(".tfvars.example")
            ):
                continue
            try:
                if file_path.stat().st_size > 100_000:
                    continue
                content = file_path.read_text(encoding="utf-8", errors="replace")
                rel = file_path.relative_to(path)
                files.append({"filename": str(rel).replace("\\", "/"), "content": content})
            except Exception as exc:
                logger.warning("Could not read %s: %s", file_path, exc)

        logger.info("Read %d %s file(s) from %s", len(files), purpose, folder_path)
        return files

    # ── generator nodes ───────────────────────────────────────────────────────

    def _read_existing_node(self, state: AgentState) -> dict:
        existing = self._read_files_from_folder(
            state.get("input_sandbox_path", ""), "existing"
        )
        # Clear clarification from a prior iteration so it isn't re-injected into
        # the generation prompt as if it were still pending.
        return {"existing_files": existing, "clarification": None}

    def _read_reference_node(self, state: AgentState) -> dict:
        reference = self._read_files_from_folder(
            state.get("reference_folder", ""), "reference"
        )
        return {"reference_files": reference}

    def _analyze_node(self, state: AgentState) -> dict:
        action = state["action"]
        reference_files = state.get("reference_files") or []
        existing_files = state.get("existing_files") or []

        ref_ctx = ""
        if reference_files:
            ref_list = "\n".join(f"  - {f['filename']}" for f in reference_files)
            ref_ctx = (
                f"\n\nREFERENCE FILES (Match their style, naming, and structure):\n{ref_list}"
            )

        existing_ctx = ""
        if existing_files:
            existing_ctx = "\n\nEXISTING FILES (Update these):\n" + "\n".join(
                f"  - {f['filename']}" for f in existing_files
            )

        prompt = f"""You are an AWS automation engineer. Analyze this action request.

Action Name: {action["actionName"]}
Action Description: {action["actionDescription"]}
Steps: {json.dumps(action.get("steps") or [], indent=2)}{ref_ctx}{existing_ctx}

Determine:
1. needs_clarification (True only if critical info is missing)
2. recommended_approach: 'python' | 'terraform' | 'both'
3. reasoning

Be conservative with clarification requests."""

        try:
            structured_llm = self.Llm.with_structured_output(ActionAnalysis)
            analysis: ActionAnalysis = structured_llm.invoke([HumanMessage(content=prompt)])
            return {"analysis": analysis.model_dump()}
        except Exception as exc:
            logger.exception("Analysis failed: %s", exc)
            raise

    def _hitl_node(self, state: AgentState) -> dict:
        questions: List[str] = state["analysis"].get("questions") or []
        # FIX: guard against LLM setting needs_clarification=True with no questions
        if not questions:
            logger.warning(
                "_hitl_node reached with empty questions list — "
                "bypassing interrupt and proceeding to generate"
            )
            return {"clarification": None}

        answers = interrupt(questions)
        answers_list = answers if isinstance(answers, list) else [answers]
        return {
            "clarification": {
                "questions": questions,
                "answers": answers_list,
            }
        }

    def _generate_node(self, state: AgentState) -> dict:
        action = state["action"]
        analysis = state["analysis"]
        clarification = state.get("clarification")
        existing_files = state.get("existing_files") or []
        reference_files = state.get("reference_files") or []
        feedback = state.get("feedback_summary") or ""

        os_name = platform.system()

        # Reference context
        reference_context = ""
        if reference_files:
            ref_dump = "\n\n".join(
                f"=== REFERENCE: {f['filename']} ===\n{f['content']}"
                for f in reference_files[:6]
            )
            reference_context = (
                "\nIMPORTANT: Follow the coding style, structure, variable naming, and best "
                f"practices from these reference files:\n\n{ref_dump}\n"
            )

        # Existing files context
        existing_context = ""
        if existing_files:
            existing_context = "\n\nEXISTING FILES TO UPDATE:\n" + "\n\n".join(
                f"=== {f['filename']} ===\n{f['content']}" for f in existing_files
            )

        # FIX: use zip_longest so every question gets a paired answer in the prompt,
        # even if the user supplied fewer answers than questions.
        clarification_context = ""
        if clarification:
            qa_lines = "\n".join(
                f"Q: {q}\nA: {a if a is not None else '(no answer provided)'}"
                for q, a in zip_longest(
                    clarification["questions"], clarification["answers"]
                )
            )
            clarification_context = f"\n\nCLARIFICATIONS:\n{qa_lines}"

        feedback_context = (
            f"\n\nPREVIOUS EXECUTION FEEDBACK (MUST FIX):\n{feedback}" if feedback else ""
        )

        mode_instruction = (
            "UPDATE the existing files shown below while preserving their structure."
            if existing_files
            else "Generate complete, production-ready code from scratch."
        )

        shell_note = (
            "The executableSteps will run via subprocess with shell=True on WINDOWS (cmd.exe), "
            "inheriting the parent process's environment variables."
            if os_name == "Windows"
            else (
                "The executableSteps will run via subprocess with shell=True on a POSIX shell, "
                "inheriting the parent process's environment variables."
            )
        )
        creds_note = (
            "AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION / "
            "AWS_SESSION_TOKEN if applicable) are ALREADY loaded into the environment via dotenv "
            "and are automatically inherited by every executed command. "
            "DO NOT generate steps to set, export, or configure AWS credentials — terraform and "
            "boto3 will pick them up automatically."
        )

        prompt = f"""You are an AWS automation engineer. {mode_instruction}

Action Name: {action["actionName"]}
Action Description: {action["actionDescription"]}
Steps: {json.dumps(action.get("steps") or [], indent=2)}
Recommended approach: {analysis["recommended_approach"]}
Execution environment: {os_name}. {shell_note} {creds_note}
{reference_context}{clarification_context}{feedback_context}{existing_context}

Requirements:
- All files must be complete and runnable
- Match the style from reference files exactly
- Python: use boto3 + argparse
- Terraform: proper module structure with variables
- CRITICAL (Terraform): each of `provider`, `terraform {{}}` (required_providers/backend), and
  any given `output` name must be defined EXACTLY ONCE across the entire file set. When updating
  existing files, check ALL existing files before adding new blocks — do not redeclare a
  provider/output that already exists in another file.
- CRITICAL (Terraform provider block): the AWS provider only supports documented arguments
  (region, profile, assume_role, default_tags, max_retries, endpoints, etc.).
  DO NOT invent arguments like `timeout_client` or `timeout_server` — these are not valid and
  will cause `terraform validate` to fail. Timeout issues are execution-time problems;
  leave the provider block unchanged in that case.
- CRITICAL (Terraform vars file): write `terraform.tfvars.example` with placeholder values
  (e.g. db_password = "CHANGE_ME"), NOT a real `terraform.tfvars`. Required variables should
  have sensible defaults in `variables.tf` or be passed via -var so `terraform plan`/`apply`
  can run without a tfvars file.
- Include all necessary executable steps
- CRITICAL: If feedback mentions a specific error or fix, apply it immediately

Generate the complete set of files."""

        try:
            structured_llm = self.Llm.with_structured_output(CodeGenerationResult)
            result: CodeGenerationResult = structured_llm.invoke([HumanMessage(content=prompt)])
            return {
                "generated_files": [f.model_dump() for f in result.files],
                "executable_steps": [s.model_dump() for s in result.executableSteps],
                "generator_summary": result.summary,
            }
        except Exception as exc:
            logger.exception("Generation failed: %s", exc)
            raise

    def _write_files_node(self, state: AgentState) -> dict:
        input_path = state.get("input_sandbox_path") or ""
        if input_path:
            sandbox_dir = input_path
            Path(sandbox_dir).mkdir(parents=True, exist_ok=True)
        else:
            # FIX: use secrets.token_hex for a collision-resistant directory name
            sandbox_dir = f"sandbox_{secrets.token_hex(6)}"
            Path(sandbox_dir).mkdir(parents=True, exist_ok=True)

        toolkit = FileManagementToolkit(root_dir=sandbox_dir)
        write_tool = {t.name: t for t in toolkit.get_tools()}["write_file"]

        for file_info in state["generated_files"]:
            filename = file_info["filename"]
            if filename.endswith(".tfvars") and filename.lower() != "terraform.tfvars":
                logger.warning(
                    "Possible filename typo: '%s' — expected 'terraform.tfvars'", filename
                )
            write_tool.invoke({"file_path": filename, "text": file_info["content"]})
            logger.info("Wrote %s", filename)


        # Keep input_sandbox_path in sync so the next iteration's read_existing
        # picks up the freshly-written files.
        return {"sandbox_path": sandbox_dir, "input_sandbox_path": sandbox_dir}

    # ── executor nodes ────────────────────────────────────────────────────────

    def _scan_folder_node(self, state: AgentState) -> dict:
        execute_folder = state["sandbox_path"]
        logger.info("Scanning folder: %s", execute_folder)
        folder_path = Path(execute_folder)
        if not folder_path.exists():
            raise FileNotFoundError(f"sandbox_path not found: {execute_folder}")

        contents = sorted(
            str(p.relative_to(folder_path))
            for p in folder_path.rglob("*")
            if p.is_file()
        )
        folder_contents = "\n".join(contents) if contents else "(empty folder)"
        logger.info("Found %d file(s) in %s", len(contents), execute_folder)
        return {"folder_contents": folder_contents}

    def _plan_node(self, state: AgentState) -> dict:
        action = state["action"]
        execute_folder = state["sandbox_path"]
        folder_contents = state.get("folder_contents") or ""

        logger.info("=" * 80)
        logger.info("PLANNING EXECUTION STRATEGY")
        logger.info("=" * 80)

        # Fast path: generator already supplied steps — no LLM call needed
        if state.get("executable_steps"):
            steps = state["executable_steps"]
            logger.info("✓ Using %d executable steps from generator", len(steps))
            logger.info("-" * 80)
            for idx, step in enumerate(steps, 1):
                logger.info("   [%d] %s", idx, step.get("description", step.get("command", "")))
            logger.info("-" * 80)
            commands = [
                {
                    "command": step.get("command") or step.get("cmd") or "",
                    "description": step.get("description", ""),
                    "working_dir": ".",
                    "order": i + 1,
                }
                for i, step in enumerate(steps)
            ]
            return {
                "execution_plan": {
                    "execution_type": "mixed",
                    "commands": commands,
                    "reasoning": "Steps provided by generator node.",
                }
            }

        # Slow path: ask LLM to derive a plan from the folder contents
        logger.info("Planning for action: %s", action.get("actionName"))
        os_name = platform.system()
        shell_note = (
            "Commands run via subprocess with shell=True on WINDOWS (cmd.exe)."
            if os_name == "Windows"
            else "Commands run via subprocess with shell=True on a POSIX shell."
        )
        creds_note = (
            "AWS credentials are ALREADY in the environment via dotenv. "
            "DO NOT generate steps to set or export AWS credentials."
        )

        toolkit = FileManagementToolkit(root_dir=execute_folder)
        read_tool = {t.name: t for t in toolkit.get_tools()}["read_file"]
        readable_exts = {".py", ".tf", ".sh", ".yaml", ".yml", ".json", ".tfvars"}

        file_previews: List[str] = []
        for rel_path in folder_contents.splitlines():
            rel_path = rel_path.strip()
            if not rel_path or Path(rel_path).suffix not in readable_exts:
                continue
            try:
                content = read_tool.invoke({"file_path": rel_path})

                
                lines = content.splitlines()
                preview = "\n".join(lines[:60])
                if len(lines) > 60:
                    preview += f"\n... ({len(lines) - 60} more lines)"
                file_previews.append(f"=== {rel_path} ===\n{preview}")
            except Exception:
                pass

        file_context = "\n\n".join(file_previews) or "(no readable source files)"

        prompt = f"""You are an AWS automation engineer. Create an execution plan for the files in this folder.

Action Name: {action["actionName"]}
Action Description: {action["actionDescription"]}
Steps: {json.dumps(action.get("steps") or [], indent=2)}

Execution environment: {os_name}. {shell_note} {creds_note}

Files in execute_folder:
{folder_contents}

File contents preview:
{file_context}

Create a detailed execution plan:

1. execution_type: "python" | "terraform" | "shell" | "mixed"

2. commands — ordered list. Follow these workflows:
   Terraform: terraform init → terraform validate → terraform plan → terraform apply -auto-approve
   Python:    pip install -r requirements.txt (if present) → python <script>.py [args]
   Shell:     chmod +x <script>.sh → ./<script>.sh

3. reasoning — one or two sentences.

Only include commands needed for the actual files present."""

        try:
            structured_llm = self.Llm.with_structured_output(ExecutionPlan)
            plan: ExecutionPlan = structured_llm.invoke([HumanMessage(content=prompt)])
            logger.info("✓ EXECUTION PLAN — type=%s  commands=%d", plan.execution_type, len(plan.commands))
            logger.info("  Reasoning: %s", plan.reasoning)
            for cmd in plan.commands:
                logger.info("  [%d] %s | %s", cmd.order, cmd.description, cmd.command)
            return {"execution_plan": plan.model_dump()}
        except Exception as exc:
            logger.exception("Execution planning failed: %s", exc)
            raise

    def _validate_command(self, command: str, execute_folder: str) -> Tuple[bool, str]:
        """Pre-execution validation. Returns (is_valid, error_message)."""
        base_path = Path(execute_folder).resolve()
        match = re.search(r'-var-file="?([^"\s]+)"?', command)
        if match:
            var_file = match.group(1)
            if not (base_path / var_file).exists():
                return False, f"Variable file does not exist: {var_file}"
        return True, ""

    def _execute_node(self, state: AgentState) -> dict:
        execute_folder = state["sandbox_path"]
        plan = state["execution_plan"]
        _raw_timeout = state.get("command_timeout")
        timeout: int = (
            _raw_timeout
            if isinstance(_raw_timeout, int) and _raw_timeout > 0
            else DEFAULT_COMMAND_TIMEOUT
        )

        if not plan or not plan.get("commands"):
            logger.error("No execution plan / commands found — skipping execution")
            return {"execution_results": [], "success": False}

        base_path = Path(execute_folder).resolve()
        total_commands = len(plan["commands"])
        results: List[Dict] = []

        logger.info("=" * 80)
        logger.info(
            "EXECUTION STARTED: %d command(s) in %s  [timeout=%ds/cmd]",
            total_commands, execute_folder, timeout,
        )
        logger.info("=" * 80)

        for idx, cmd_info in enumerate(
            sorted(plan["commands"], key=lambda c: c.get("order", 9999)), 1
        ):
            command: str = cmd_info["command"]
            description: str = cmd_info.get("description", "")
            relative_dir: str = cmd_info.get("working_dir", ".")

            cwd = (base_path / relative_dir).resolve()
            if not cwd.exists():
                cwd = base_path

            # Pre-execution validation
            is_valid, error_msg = self._validate_command(command, str(cwd))
            if not is_valid:
                logger.warning("[%d/%d] ✗ VALIDATION FAILED: %s", idx, total_commands, description or command)
                logger.warning("        Validation Error: %s", error_msg)
                results.append({
                    "command": command,
                    "description": description,
                    "working_dir": str(cwd),
                    "stdout": "",
                    "stderr": f"Pre-execution validation failed: {error_msg}",
                    "return_code": -1,
                    "success": False,
                    "timed_out": False,
                    "timeout_seconds": timeout,
                })
                logger.error(
                    "EXECUTION HALTED (VALIDATION FAILED): %d remaining command(s) skipped",
                    total_commands - idx,
                )
                break

            logger.info("-" * 80)
            logger.info("[%d/%d] EXECUTING: %s", idx, total_commands, description or command)
            logger.info("        Command    : %s", command)
            logger.info("        Working Dir: %s", cwd)
            logger.info("        Timeout    : %ds", timeout)
            logger.info("-" * 80)

            timed_out = False
            result: Dict[str, Any]

            try:
                # Invoke the LangChain tool
                tool_output = execute_shell_command.invoke({
                    "command": command,
                    "cwd": str(cwd),
                    "timeout": timeout
                })

                success = tool_output["return_code"] == 0
                stdout_data = tool_output["stdout"]
                stderr_data = tool_output["stderr"]
                proc_returncode = tool_output["return_code"]


                result = {
                    "command": command,
                    "description": description,
                    "working_dir": str(cwd),
                    "stdout": stdout_data[:10_000],
                    "stderr": stderr_data[:8_000],
                    "return_code": proc_returncode,
                    "success": success,
                    "timed_out": False,
                    "timeout_seconds": timeout,
                }

                if success:
                    logger.info(
                        "[%d/%d] ✓ SUCCESS: %s (rc=%d)",
                        idx, total_commands, description or command, proc_returncode,
                    )
                    if stdout_data:
                        logger.info(
                            "        Output: %s%s",
                            stdout_data[:300],
                            "..." if len(stdout_data) > 300 else "",
                        )
                else:
                    logger.warning(
                        "[%d/%d] ✗ FAILED: %s (rc=%d)",
                        idx, total_commands, description or command, proc_returncode,
                    )
                    logger.warning("        Error: %s", stderr_data[:500])

            except TimeoutError as exc:

                timed_out = True
                stderr_data = str(exc)
                timeout_msg = (
                    f"Command '{command}' timed out after {timeout}s. "
                    f"Step '{description}' did not complete within the allowed time. "
                    "If this is 'terraform init', it is likely a slow provider-plugin download "
                    "on first run (not a code or credentials issue) — DO NOT add invalid provider "
                    "arguments like 'timeout_client'/'timeout_server'. "
                    "If this is 'terraform plan'/'apply', check AWS credentials or network access. "
                    "The orchestrator will retry automatically; no code change is needed."
                )
                result = {
                    "command": command,
                    "description": description,
                    "working_dir": str(cwd),
                    "stdout": "",
                    "stderr": timeout_msg,
                    "return_code": -1,
                    "success": False,
                    "timed_out": True,
                    "timeout_seconds": timeout,
                }
                logger.error(
                    "[%d/%d] ✗ TIMEOUT: %s exceeded %ds",
                    idx, total_commands, description or command, timeout,
                )

            except CommandFailedError as exc:
                result = {
                    "command": command,
                    "description": description,
                    "working_dir": str(cwd),
                    "stdout": exc.stdout[:10_000],
                    "stderr": exc.stderr[:8_000],
                    "return_code": exc.rc,
                    "success": False,
                    "timed_out": False,
                    "timeout_seconds": timeout,
                }
                logger.warning(
                    "[%d/%d] ✗ FAILED: %s (rc=%d)",
                    idx, total_commands, description or command, exc.rc,
                )
                logger.warning("        Error: %s", exc.stderr[:500])

            except Exception as exc:
                result = {
                    "command": command,
                    "description": description,
                    "working_dir": str(cwd),
                    "stdout": "",
                    "stderr": str(exc),
                    "return_code": -1,
                    "success": False,
                    "timed_out": False,
                    "timeout_seconds": timeout,
                }
                logger.exception(
                    "[%d/%d] ✗ EXCEPTION in '%s': %s",
                    idx, total_commands, description or command, exc,
                )

            results.append(result)

            if not result["success"]:
                halt_reason = "TIMEOUT" if timed_out else "COMMAND FAILED"
                logger.error(
                    "EXECUTION HALTED (%s): %d remaining command(s) skipped",
                    halt_reason, total_commands - idx,
                )
                break

        overall_success = (
            bool(results)
            and all(r["success"] for r in results)
            and len(results) == total_commands
        )

        logger.info("=" * 80)
        if overall_success:
            logger.info("✓ EXECUTION COMPLETED SUCCESSFULLY: All %d command(s) ran", len(results))
        else:
            timed_out_count = sum(1 for r in results if r.get("timed_out"))
            if timed_out_count:
                logger.warning("✗ EXECUTION: %d command(s) timed out", timed_out_count)
            else:
                logger.warning(
                    "✗ EXECUTION: %d/%d command(s) succeeded",
                    sum(1 for r in results if r["success"]), len(results),
                )
        logger.info("=" * 80)

        return {"execution_results": results, "success": overall_success}

    def _report_node(self, state: AgentState) -> dict:
        action = state["action"]
        results = state.get("execution_results") or []
        success = state.get("success", False)
        timeout = state.get("command_timeout") or DEFAULT_COMMAND_TIMEOUT

        logger.info("=" * 80)
        logger.info("GENERATING EXECUTION REPORT")
        logger.info("Action: %s | Status: %s", action.get("actionName"), "SUCCESS" if success else "FAILED")
        logger.info(
            "Commands: %d total, %d succeeded, %d failed",
            len(results),
            sum(1 for r in results if r["success"]),
            sum(1 for r in results if not r["success"]),
        )
        logger.info("=" * 80)

        parts = []
        for r in results:
            status_label = (
                "SUCCESS" if r["success"] else ("TIMED OUT" if r.get("timed_out") else "FAILED")
            )
            entry = [
                f"Command    : {r['command']}",
                f"Status     : {status_label} (rc={r['return_code']})",
            ]
            if r.get("timed_out"):
                entry.append(
                    f"Timeout    : exceeded {r.get('timeout_seconds', timeout)}s — "
                    "process was killed"
                )
            entry.append(f"Output     : {r['stdout'][:500] or '(none)'}")
            entry.append(f"Errors     : {r['stderr'][:300] or '(none)'}")
            parts.append("\n".join(entry))

        results_text = "\n\n".join(parts) or "(no commands were executed)"
        any_timed_out = any(r.get("timed_out") for r in results)

        timeout_rule = (
            f"- One or more commands TIMED OUT. Explicitly state which command timed out "
            f"and that it exceeded the {timeout}s limit."
            if any_timed_out
            else (
                "- NO command timed out (timed_out=false for all results). DO NOT use the phrase "
                "'timed out'. Describe the ACTUAL error from the 'Errors' field."
            )
        )

        prompt = f"""Summarize the execution of this AWS automation action in 2–4 sentences.

Action: {action["actionName"]}
Description: {action["actionDescription"]}
Overall Success: {success}
Per-command timeout: {timeout}s

Execution Results:
{results_text}

Rules:
{timeout_rule}
- Name exact argument/error from the 'Errors' field — do not invent errors.
- Cover: what ran, whether it succeeded, resource IDs created, concrete next steps on failure."""

        try:
            response = self.Llm.invoke([HumanMessage(content=prompt)])
            summary = response.content
            logger.info("✓ LLM summary generated")
        except Exception as exc:
            logger.warning("LLM summary failed, using fallback: %s", exc)
            timed_out_cmds = [r for r in results if r.get("timed_out")]
            if timed_out_cmds:
                names = ", ".join(f"'{r['command']}'" for r in timed_out_cmds)
                summary = (
                    f"Execution of '{action['actionName']}' failed: {names} timed out after "
                    f"{timeout}s. Check AWS credentials and network access, then retry."
                )
            else:
                succeeded = sum(1 for r in results if r["success"])
                summary = (
                    f"Executed {succeeded}/{len(results)} command(s) for "
                    f"'{action['actionName']}'. "
                    + ("All steps completed successfully." if success else "Some commands failed — review stderr.")
                )

        return {"executor_summary": summary}

    # ── orchestration node ────────────────────────────────────────────────────

    def _record_iteration_node(self, state: AgentState) -> dict:
        iteration = state["iteration"]
        records = list(state.get("records") or [])

        record = IterationRecord(
            iteration=iteration,
            generator_status="success",
            executor_status="success" if state.get("success") else "failed",
            executor_success=bool(state.get("success")),
            feedback_used=state.get("feedback_summary") or None,
            sandbox_path=state.get("sandbox_path"),
        )
        records.append(record.model_dump())

        if state.get("success"):
            self._banner(f"✓ PIPELINE COMPLETED SUCCESSFULLY on iteration {iteration}", char="═")
            return {
                "records": records,
                "final_status": "success",
                "final_summary": state.get("executor_summary"),
            }

        max_iter = state.get("max_iterations", MAX_ITERATIONS)
        if iteration >= max_iter:
            self._banner(f"✗ PIPELINE EXHAUSTED {max_iter} ITERATIONS WITHOUT SUCCESS", char="═")
            last_raw_error = ""
            for r in state.get("execution_results") or []:
                if not r.get("success"):
                    last_raw_error = (
                        f"Command '{r['command']}' failed "
                        f"(rc={r['return_code']}"
                        f"{', timed out' if r.get('timed_out') else ''}).\n"
                        f"stderr: {r['stderr'][:1000]}"
                    )
                    break
            summary = (
                f"Action '{state['action'].get('actionName')}' could not be completed after "
                f"{iteration} iteration(s).\n"
                f"Last error: {last_raw_error or '(no execution results)'}\n"
                f"AI summary: {state.get('executor_summary')}"
            )
            return {"records": records, "final_status": "failed", "final_summary": summary}

        # Build feedback for the next iteration — raw stderr takes priority over
        # the LLM summary, which can drift on repeated retries.
        raw_error = ""
        for r in state.get("execution_results") or []:
            if not r.get("success"):
                raw_error = (
                    f"Command '{r['command']}' failed (rc={r['return_code']}).\n"
                    f"stderr:\n{r['stderr'][:6000]}"
                )
                break

        feedback_parts: List[str] = []
        if raw_error:
            feedback_parts.append(
                f"EXACT ERROR OUTPUT (ground truth — fix THIS):\n{raw_error}"
            )
        if state.get("executor_summary"):
            feedback_parts.append(
                f"AI-generated summary (may be inaccurate; exact error above takes priority):\n"
                f"{state['executor_summary']}"
            )

        feedback = "\n\n".join(feedback_parts) or (
            f"Execution failed on iteration {iteration}. "
            "Review the error output and fix the generated files."
        )
        logger.info(
            "[Iteration %d] Feedback: %s",
            iteration,
            feedback[:300] + "..." if len(feedback) > 300 else feedback,
        )
        return {
            "records": records,
            "iteration": iteration + 1,
            "feedback_summary": feedback,
            "final_status": "in_progress",
        }

    # ── routing ───────────────────────────────────────────────────────────────

    @staticmethod
    def _route_after_analysis(state: AgentState) -> str:
        if state["analysis"]["needs_clarification"]:
            return "hitl"
        return "generate"

    @staticmethod
    def _route_after_record(state: AgentState) -> str:
        if state.get("final_status") in ("success", "failed"):
            return "end"
        return "retry"

    # ── graph construction ────────────────────────────────────────────────────

    def _build_graph(self):
        builder = StateGraph(AgentState)

        # generator nodes
        builder.add_node("read_existing", self._read_existing_node)
        builder.add_node("read_reference", self._read_reference_node)
        builder.add_node("analyze", self._analyze_node)
        builder.add_node("hitl", self._hitl_node)
        builder.add_node("generate", self._generate_node)
        builder.add_node("write_files", self._write_files_node)

        # executor nodes
        builder.add_node("scan_folder", self._scan_folder_node)
        builder.add_node("plan", self._plan_node)
        builder.add_node("execute", self._execute_node)
        builder.add_node("report", self._report_node)

        # orchestration node
        builder.add_node("record_iteration", self._record_iteration_node)

        builder.set_entry_point("read_existing")
        builder.add_edge("read_existing", "read_reference")
        builder.add_edge("read_reference", "analyze")
        builder.add_conditional_edges(
            "analyze",
            self._route_after_analysis,
            {"hitl": "hitl", "generate": "generate"},
        )
        builder.add_edge("hitl", "generate")
        builder.add_edge("generate", "write_files")
        builder.add_edge("write_files", "scan_folder")
        builder.add_edge("scan_folder", "plan")
        builder.add_edge("plan", "execute")
        builder.add_edge("execute", "report")
        builder.add_edge("report", "record_iteration")
        builder.add_conditional_edges(
            "record_iteration",
            self._route_after_record,
            {"end": END, "retry": "read_existing"},
        )

        return builder.compile(checkpointer=self.Checkpointer)

    # ── public API ────────────────────────────────────────────────────────────

    def RunPipeline(
        self,
        action: Dict[str, Any],
        sandbox_path: Optional[str] = None,
        reference_folder: Optional[str] = None,
        thread_id: Optional[str] = None,
        answers: Optional[List[str]] = None,
        command_timeout: int = DEFAULT_COMMAND_TIMEOUT,
    ) -> PipelineResponse:
        """
        Run the generate → execute → (retry on failure) loop until success or
        max_iterations is exhausted, all within a single agent / single graph.

        Pass ``answers`` (non-empty list) together with the original ``thread_id``
        to resume a ``needs_clarification`` pause.
        """
        tid = thread_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": tid}}

        logger.info("")
        self._banner("UNIFIED AGENT PIPELINE STARTED")
        logger.info("Thread ID        : %s", tid)
        logger.info("Action           : %s", action.get("actionName"))
        logger.info("Reference Folder : %s", reference_folder or "None")
        logger.info("Max Iterations   : %d", self.max_iterations)
        logger.info("Command Timeout  : %ds per command", command_timeout)
        logger.info("")

        try:
            # FIX: only resume when answers is a non-empty list to avoid
            # accidentally triggering resume with an empty []
            if answers:
                self.Graph.invoke(Command(resume=answers), config=config)
            else:
                self.Graph.invoke(
                    {
                        "action": action,
                        "reference_folder": reference_folder or "",
                        "command_timeout": command_timeout,
                        "max_iterations": self.max_iterations,
                        "iteration": 1,
                        "records": [],
                        "feedback_summary": "",

                        "analysis": None,
                        "clarification": None,
                        "generated_files": [],
                        "executable_steps": [],
                        "sandbox_path": "",
                        "existing_files": [],
                        "reference_files": [],
                        "input_sandbox_path": sandbox_path or "",
                        "generator_summary": "",

                        "folder_contents": None,
                        "execution_plan": None,
                        "execution_results": [],
                        "success": False,
                        "executor_summary": "",

                        "final_status": "in_progress",
                        "final_summary": "",
                    },
                    config=config,
                )

            snapshot = self.Graph.get_state(config)

            # HITL pause — graph is suspended, waiting for answers
            if snapshot.tasks and any(t.interrupts for t in snapshot.tasks):
                questions = snapshot.tasks[0].interrupts[0].value
                return PipelineResponse(
                    statusCode=202,
                    status="needs_clarification",
                    thread_id=tid,
                    sandbox_path=snapshot.values.get("sandbox_path") or None,
                    iterations_used=snapshot.values.get("iteration", 1),
                    iterations=[
                        IterationRecord(**r) for r in snapshot.values.get("records", [])
                    ],
                    questions=questions,
                    summary=(
                        f"Agent needs clarification (thread_id={tid}). "
                        f"Re-call RunPipeline with answers=[...] and thread_id='{tid}'."
                    ),
                )

            final = snapshot.values
            records = [IterationRecord(**r) for r in final.get("records", [])]
            results = [ExecutionResult(**r) for r in final.get("execution_results", [])]
            final_status = final.get("final_status", "failed")
            sandbox_path_final: Optional[str] = final.get("sandbox_path") or None

            if final_status == "success":
                # Sandbox intentionally kept: contains terraform.tfstate and applied configs
                # needed for future updates / `terraform destroy`.
                return PipelineResponse(
                    statusCode=200,
                    status="success",
                    thread_id=tid,
                    sandbox_path=sandbox_path_final,
                    iterations_used=final.get("iteration", len(records)),
                    iterations=records,
                    execution_results=results,
                    summary=final.get("final_summary") or final.get("executor_summary"),
                )

            # failed / exhausted
            self._cleanup_sandbox(sandbox_path_final)
            return PipelineResponse(
                statusCode=207,
                status="failed",
                thread_id=tid,
                sandbox_path=sandbox_path_final,
                iterations_used=final.get("iteration", len(records)),
                iterations=records,
                execution_results=results,
                summary=final.get("final_summary") or final.get("executor_summary"),
            )

        except Exception as exc:
            logger.exception("RunPipeline error: %s", exc)
            return PipelineResponse(
                statusCode=500,
                status="error",
                exception=str(exc),
                thread_id=tid,
            )



if __name__ == "__main__":
    # --- Arize Phoenix Setup ---
    import phoenix as px
    from phoenix.otel import register
    from openinference.instrumentation.langchain import LangChainInstrumentor
    
    # 1. Start the local Phoenix dashboard server
    session = px.launch_app()
    
    # 2. Native Phoenix v4 Tracing Setup: Connect OpenTelemetry directly to the active session
    tracer_provider = register()
    
    # 3. Tell Phoenix to automatically track all LangChain/LangGraph tools
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
    # ---------------------------
    
    agent = ExecutionAgents(max_iterations=2)

    action_payload = {
        "actionName": "Deploy Production RDS Instance with Terraform",
        "actionDescription": (
            "Deploy a single-AZ PostgreSQL RDS instance (REL-001) tagged as production "
            "in the default VPC using Terraform. This provisions the database infrastructure "
            "with storage encryption enabled and applies production environment tags."
        ),
        "steps": [],
    }

    from opentelemetry import trace
    from opentelemetry.trace.status import Status, StatusCode
    
    tracer = trace.get_tracer(__name__)
    
    with tracer.start_as_current_span("ExecutionAgents_Execution") as span:
        # Run the agent
        response = agent.RunPipeline(
            action=action_payload,
            reference_folder="",
            command_timeout=180,
        )
        
        # Inject the exact Execution Dimension metrics into Phoenix
        span.set_attribute("agent.execution_status", response.status)
        span.set_attribute("agent.iterations_used", response.iterations_used)
        
        # If the agent failed to achieve its goal, force the UI to show a RED Error status!
        if response.status != "success":
            span.set_status(Status(StatusCode.ERROR, description=f"Agent failed after {response.iterations_used} iterations"))

    print(response.model_dump_json(indent=2))

    # Keep the script alive so the Phoenix dashboard doesn't shut down immediately
    print("\n" + "="*80)
    print("Phoenix dashboard is LIVE at http://localhost:6006/")
    print("="*80)
    input("Press Enter to exit and close the dashboard...")

