"""BoxPwnr-based CTF agent runner.

Wraps BoxPwnr's Solver to run CTF challenges using LLM agents.
Defaults to BoxPwnr, but resolves it generically from:
1) installed Python package
2) optional env-configured source paths
3) local references/ fallback paths
"""

import importlib
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _default_boxpwnr_source_candidates() -> list[Path]:
    """Return candidate source roots that may contain ``boxpwnr`` package."""
    repo_root = Path(__file__).resolve().parents[3]
    raw_candidates = [
        os.getenv("TRAJGYM_BOXPWNR_SRC", "").strip(),
        os.getenv("TRAJGYM_DEFAULT_AGENT_SRC", "").strip(),
        str(repo_root / "references" / "boxpwnr" / "src"),
        str(repo_root / "references" / "BoxPwnr" / "src"),
    ]
    paths: list[Path] = []
    seen: set[str] = set()
    for raw in raw_candidates:
        if not raw:
            continue
        p = Path(raw).expanduser().resolve()
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        paths.append(p)
    return paths


def _boxpwnr_import_origin() -> str:
    """Return best-effort origin string for the imported ``boxpwnr`` package."""
    try:
        mod = importlib.import_module("boxpwnr")
        origin = getattr(mod, "__file__", None)
        if origin:
            return str(Path(origin).resolve())
    except Exception:
        pass
    return "python-path"


def _import_boxpwnr() -> tuple[object, object, object, object, object, str]:
    """Import BoxPwnr components and return (classes..., resolved_source)."""
    # Prefer installed package/import path first for maximum portability.
    try:
        from boxpwnr.core.solver import Solver
        from boxpwnr.executors.docker.docker_executor import DockerExecutor
        from boxpwnr.strategies import (
            ChatCompletionStrategy,
            ChatCompletionToolsStrategy,
        )
        from boxpwnr.utils.secrets_manager import SecretManager

        return (
            Solver,
            DockerExecutor,
            ChatCompletionToolsStrategy,
            ChatCompletionStrategy,
            SecretManager,
            _boxpwnr_import_origin(),
        )
    except ImportError as first_exc:
        last_exc = first_exc

    attempted: list[str] = []
    for candidate in _default_boxpwnr_source_candidates():
        attempted.append(str(candidate))
        if not candidate.exists():
            continue
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        try:
            from boxpwnr.core.solver import Solver
            from boxpwnr.executors.docker.docker_executor import DockerExecutor
            from boxpwnr.strategies import (
                ChatCompletionStrategy,
                ChatCompletionToolsStrategy,
            )
            from boxpwnr.utils.secrets_manager import SecretManager

            return (
                Solver,
                DockerExecutor,
                ChatCompletionToolsStrategy,
                ChatCompletionStrategy,
                SecretManager,
                str(candidate),
            )
        except ImportError as exc:
            last_exc = exc

    raise ImportError(
        "Could not import BoxPwnr. Install `boxpwnr` in the active environment "
        "or set TRAJGYM_BOXPWNR_SRC to a source path containing `boxpwnr/`. "
        f"Attempted sources: {attempted or ['<none>']}. "
        f"Original error: {last_exc}"
    ) from last_exc


def _get_platform(
    platform_name: str, executor, traces_dir: str, keep_target: bool = False
):
    """Create a BoxPwnr platform instance by name."""
    if platform_name == "xbow":
        from boxpwnr.platforms.xbow import XBOWPlatform

        return XBOWPlatform(
            executor=executor, traces_dir=traces_dir, keep_target=keep_target
        )
    elif platform_name == "local":
        from boxpwnr.platforms.local import LocalPlatform

        return LocalPlatform(
            executor=executor, traces_dir=traces_dir, keep_target=keep_target
        )
    elif platform_name == "htb":
        from boxpwnr.platforms.htb import HTBPlatform

        return HTBPlatform(
            executor=executor, traces_dir=traces_dir, keep_target=keep_target
        )
    elif platform_name == "portswigger":
        from boxpwnr.platforms.portswigger import PortSwiggerPlatform

        return PortSwiggerPlatform(
            executor=executor, traces_dir=traces_dir, keep_target=keep_target
        )
    elif platform_name == "cybench":
        from boxpwnr.platforms.cybench import CybenchPlatform

        return CybenchPlatform(
            executor=executor, traces_dir=traces_dir, keep_target=keep_target
        )
    else:
        raise ValueError(
            f"Unknown platform: {platform_name}. "
            f"Supported: xbow, local, htb, portswigger, cybench"
        )


class AgentRunner:
    """Runs BoxPwnr solver against CTF challenges.

    This is a thin wrapper around BoxPwnr's Solver that provides
    a simplified interface for the Open Trajectory Gym project.

    Usage:
        runner = AgentRunner(platform="xbow", model="ollama/nanbeige4.1-3b")
        runner.run(target="XBEN-003-24")
    """

    def __init__(
        self,
        platform: str = "xbow",
        model: str = "openrouter/openai/gpt-oss-120b",
        strategy: str = "chat_tools",
        max_turns: int = 50,
        max_time: int | None = 30,
        max_cost: float | None = None,
        traces_dir: str = "./targets",
        debug: bool = False,
        keep_container: bool = False,
        keep_target: bool = False,
        reasoning_effort: str = "medium",
        attempts: int = 1,
        custom_instructions: str | None = None,
    ):
        """Initialize the agent runner.

        Args:
            platform: Target platform (xbow, local, htb, portswigger, cybench).
            model: LLM model identifier (e.g. openrouter/openai/gpt-oss-120b).
            strategy: LLM strategy (chat, chat_tools).
            max_turns: Maximum conversation turns per attempt.
            max_time: Maximum time in minutes per attempt.
            max_cost: Maximum cost in USD per attempt.
            traces_dir: Directory to store trace artifacts.
            debug: Enable debug logging.
            keep_container: Keep Docker container after completion.
            keep_target: Keep target running after completion.
            reasoning_effort: Reasoning effort level for supported models.
            attempts: Number of solve attempts.
            custom_instructions: Additional instructions appended to system prompt.
        """
        self.platform_name = platform
        self.model = model
        self.strategy_name = strategy
        self.max_turns = max_turns
        self.max_time = max_time
        self.max_cost = max_cost
        self.traces_dir = traces_dir
        self.debug = debug
        self.keep_container = keep_container
        self.keep_target = keep_target
        self.reasoning_effort = reasoning_effort
        self.attempts = attempts
        self.custom_instructions = custom_instructions
        # For cybench platform, use shared_net so Kali container can
        # resolve challenge container hostnames via Docker DNS.
        self.docker_network = "shared_net" if platform == "cybench" else "bridge"

    def check_setup(self) -> bool:
        """Verify BoxPwnr components can be imported.

        Returns:
            True if all imports succeed, False otherwise.
        """
        try:
            *_, source = _import_boxpwnr()
            print(f"BoxPwnr source: {source}")
            print(f"Platform:       {self.platform_name}")
            print(f"Model:          {self.model}")
            print(f"Strategy:       {self.strategy_name}")
            print("All components OK.")
            return True
        except ImportError as e:
            print(f"Setup check failed: {e}")
            return False

    def run(self, target: str):
        """Run the solver against a target.

        Args:
            target: Target identifier (e.g. XBEN-003-24 for xbow).
        """
        (
            Solver,
            DockerExecutor,
            ChatCompletionToolsStrategy,
            ChatCompletionStrategy,
            SecretManager,
            _,
        ) = _import_boxpwnr()

        # Build traces dir with platform subdirectory
        traces_dir = f"{self.traces_dir}/{self.platform_name}"

        # Create executor
        executor = DockerExecutor(
            keep_container=self.keep_container,
            default_timeout=30,
            max_timeout=300,
            use_interactive_sessions=(self.strategy_name == "chat_tools"),
            docker_network=self.docker_network,
        )

        # Create platform
        platform = _get_platform(
            self.platform_name,
            executor=executor,
            traces_dir=traces_dir,
            keep_target=self.keep_target,
        )

        # Create secrets manager
        secrets_manager = SecretManager()

        # Create LLM strategy
        if self.strategy_name == "chat_tools":
            llm_strategy = ChatCompletionToolsStrategy(
                model=self.model,
                secrets_manager=secrets_manager,
                executor=executor,
                reasoning_effort=self.reasoning_effort,
            )
        elif self.strategy_name == "chat":
            llm_strategy = ChatCompletionStrategy(
                model=self.model,
                secrets_manager=secrets_manager,
                reasoning_effort=self.reasoning_effort,
            )
        else:
            raise ValueError(
                f"Unknown strategy: {self.strategy_name}. Supported: chat, chat_tools"
            )

        # Create and run solver
        solver = Solver(
            target_name=target,
            platform=platform,
            executor=executor,
            llm_strategy=llm_strategy,
            traces_dir=traces_dir,
            strategy_name=self.strategy_name,
            debug=self.debug,
            max_turns=self.max_turns,
            max_cost=self.max_cost,
            max_time=self.max_time,
            attempts=self.attempts,
            custom_instructions=self.custom_instructions,
        )

        return solver.solve()
