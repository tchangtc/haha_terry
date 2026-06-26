"""CLI entry point for Terry."""

from __future__ import annotations

import atexit
import os
import sys
import threading
import time
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from . import __version__
from .core.agent import Agent
from .core.config import TerryConfig
from .core.platform_utils import get_terry_dir
from .core.ux import FirstRunWizard, TipsEngine
from .i18n import get_i18n, t

# Enable readline support for command history on Unix
try:
    import readline
    _readline_available = True
except ImportError:
    _readline_available = False

try:
    import rlcompleter
except ImportError:
    rlcompleter = None

app = typer.Typer(
    name="terry",
    help="Terry - Your intelligent personal assistant",
    add_completion=False,
)
console = Console()

# ═══════════════════════════════════════════════════════════════════
# Real-time Progress Display — dynamic, varied, Claude Code-style
# ═══════════════════════════════════════════════════════════════════

# ── Marker pools per phase category (cycled for animation) ──────
_MARKERS = {
    "thinking":   ["✶", "✧", "✩", "✪", "✫", "✬", "✭", "✮", "✯", "✰"],
    "searching":  ["●", "◉", "◎", "◌", "○"],
    "reading":    ["◉", "◎", "◌", "○"],
    "writing":    ["✎", "✐", "✑", "✒", "✏"],
    "running":    ["⚙", "⚡", "⚛", "⚒"],
    "finishing":  ["✻", "✼", "✽", "✾", "✿", "❀"],
    "done":       [""],
}

# ── Verb pools — varied language rotated every ~3s ──────────────
_VERBS = {
    "thinking": [
        "Thinking", "Pondering", "Considering", "Analyzing", "Processing",
        "Reasoning", "Deliberating", "Ruminating", "Contemplating",
        "Perambulating", "Cogitating", "Mulling over",
    ],
    "deep": [
        "Deep thinking", "Reasoning in depth", "Working through", "Thinking carefully",
        "Deliberating", "Weighing options",
    ],
    "searching": [
        "Searching", "Looking for", "Scanning for", "Hunting for",
        "Exploring", "Probing", "Investigating",
    ],
    "reading": [
        "Reading", "Examining", "Inspecting", "Reviewing",
    ],
    "writing": [
        "Writing", "Editing", "Composing", "Crafting",
    ],
    "running": [
        "Running", "Executing", "Computing",
    ],
    "finishing": [
        "Finishing up", "Wrapping up", "Polishing", "Synthesizing",
        "Finalizing", "Leavening",
    ],
}

# ── Tips shown in sub-line after completion ─────────────────────
_TIPS = [
    "Tip: Use /clear to start fresh when switching topics and free up context",
    "Tip: Use /undo to revert the last file change",
    "Tip: Use /plan before big refactors to review the approach first",
    "Tip: Use @file:path to give Terry direct context about a specific file",
    "Tip: Run 'terry webui' for a visual chat interface in your browser",
    "Tip: Use /stream for real-time token-by-token responses",
    "Tip: Use /fork to explore alternative approaches",
    "Tip: Press Tab to autocomplete commands",
    "Tip: Use /search to find anything in your conversation history",
    "Tip: Use /checkpoints to browse all undo snapshots",
]


def _format_duration(seconds: float) -> str:
    """Format seconds as 'Xm Ys' or 'Ys' for short durations."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def _format_tokens(n: int) -> str:
    """Format token count for display."""
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


def _pick(items: list[str], idx: int) -> str:
    """Pick from list, cycling with index."""
    return items[idx % len(items)]


def _tool_verb(name: str) -> str:
    """Map tool name to a past-tense action verb for summaries."""
    _map = {
        "grep": "searched", "glob": "matched", "find_tool": "found",
        "ls": "listed", "ls_tool": "listed", "read_file": "read",
        "write_file": "wrote", "edit_file": "edited", "bash": "ran",
        "web_search": "searched web for", "web_fetch": "fetched",
        "todo_write": "updated tasks", "notes": "noted", "notebook": "edited notebook",
    }
    return _map.get(name, f"used {name}")


def _activity_summary(history: list[dict]) -> str:
    """Build a human-readable activity summary from tool call history.

    Example: "searched 2 patterns, read 1 file, ran 1 command"
    """
    if not history:
        return ""
    counts: dict[str, int] = {}
    for h in history:
        name = h.get("name", "unknown")
        counts[name] = counts.get(name, 0) + 1

    parts = []
    for name, n in sorted(counts.items(), key=lambda x: -x[1]):
        verb = _tool_verb(name)
        if n == 1:
            parts.append(f"{verb} 1 {_tool_noun(name)}")
        else:
            parts.append(f"{verb} {n} {_tool_noun_plural(name)}")
    return ", ".join(parts)


def _tool_noun(name: str) -> str:
    """Singular noun for a tool type."""
    return {
        "grep": "pattern", "glob": "pattern", "find_tool": "file",
        "ls": "directory", "ls_tool": "directory", "read_file": "file",
        "write_file": "file", "edit_file": "file", "bash": "command",
        "web_search": "query", "web_fetch": "page",
    }.get(name, "thing")


def _tool_noun_plural(name: str) -> str:
    """Plural noun for a tool type."""
    return {
        "grep": "patterns", "glob": "patterns", "find_tool": "files",
        "ls": "directories", "ls_tool": "directories", "read_file": "files",
        "write_file": "files", "edit_file": "files", "bash": "commands",
        "web_search": "queries", "web_fetch": "pages",
    }.get(name, "things")


class ProgressDisplay:
    """Dynamic, varied progress display with Unicode markers, playful verbs,
    activity summaries, tool sub-lines, and contextual tips.

    Writes to stderr to coexist with Rich console output on stdout.
    """

    def __init__(self) -> None:
        self.start_time = time.time()
        self.state: dict = {
            "iteration": 0,
            "tool_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "tool_name": "",
            "tool_detail": "",
        }
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._tool_history: list[dict] = []       # accumulated tool calls
        self._main_frame_idx = 0                   # increments each render
        self._verb_idx = 0                         # for cycling through verb pool
        self._last_verb_switch = 0.0               # timestamp of last verb change
        self._final_tip: str = ""                  # tip shown when done

    # ── Public API ─────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background spinner thread."""
        self._running = True
        self.start_time = time.time()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def update(self, event: str, data: dict) -> None:
        """Update display state from agent progress callback."""
        with self._lock:
            self.state.update(data)
            # Set finishing flag for rendering
            if event in ("almost_done", "done"):
                self.state["_finishing"] = True
            # Track tool calls for activity summary
            if event == "tool_executed":
                self._tool_history.append({
                    "name": str(data.get("tool_name", "")),
                    "detail": str(data.get("tool_detail", "")),
                })
            # Pick a random tip when finishing
            if event == "almost_done" and not self._final_tip:
                import random
                self._final_tip = random.choice(_TIPS)

    def stop(self) -> None:
        """Stop spinner and clear all progress lines, leaving stderr clean."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.6)
        # Always clear: main line + potential sub-line, then return cursor
        sys.stderr.write("\r\033[K")      # clear current line (main)
        sys.stderr.write("\n\r\033[K")    # down + clear (sub-line position)
        sys.stderr.write("\033[F")        # back to original line
        sys.stderr.flush()
        self._final_tip = ""

    # ── Internal rendering ─────────────────────────────────────────

    def _spin(self) -> None:
        """Spinner loop — redraws ~10 times/sec."""
        while self._running:
            with self._lock:
                self._render()
            self._main_frame_idx += 1
            time.sleep(0.1)

    def _render(self) -> None:
        """Render the current frame: a main status line + optional sub-line."""
        s = self.state
        elapsed = time.time() - self.start_time
        iteration = int(s.get("iteration", 0))

        # Rotate verb every ~3 seconds
        if elapsed - self._last_verb_switch > 3.0:
            self._verb_idx += 1
            self._last_verb_switch = elapsed

        # Determine phase category
        category = self._resolve_category(s)
        marker = _pick(_MARKERS.get(category, ["●"]), self._main_frame_idx)
        verb = self._build_verb(category, s, iteration, elapsed)

        # ── Main line ──────────────────────────────────────────────
        # Format: ✶ Thinking for 4m 30s, searching for 2 patterns, listing 1 directory… (↓ 7.7k tokens · thinking)
        elapsed_str = _format_duration(elapsed)

        # Build activity context suffix
        activity = _activity_summary(self._tool_history)
        if activity:
            label = f"{verb} for {elapsed_str}, {activity}…"
        else:
            label = f"{verb} for {elapsed_str}…"

        # Build stats
        stats = []
        out_tok = int(s.get("output_tokens", 0))
        if out_tok:
            stats.append(f"↓ {_format_tokens(out_tok)} tokens")
        cost = float(s.get("cost", 0))
        if cost > 0:
            stats.append(f"${cost:.4f}")

        # Status suffix
        if category == "finishing":
            suffix = "almost done thinking"
        elif category == "thinking" and iteration > 2:
            suffix = "thinking more"
        elif category == "thinking":
            suffix = "thinking"
        else:
            suffix = ""

        if suffix:
            if stats:
                label += f" ({' · '.join(stats)} · {suffix})"
            else:
                label += f" ({suffix})"
        elif stats:
            label += f" ({' · '.join(stats)})"

        main = f"  {marker} {label}"
        sys.stderr.write(f"\r\033[K{main}")

        # ── Sub-line ───────────────────────────────────────────────
        tool_detail = str(s.get("tool_detail", ""))
        if tool_detail and category not in ("done", "finishing"):
            sys.stderr.write(f"\n\r\033[K    ⎿  {tool_detail}\033[F")
        else:
            # Clear any leftover sub-line from a previous frame
            sys.stderr.write("\n\r\033[K\033[F")

        # Show task progress if a plan is active
        try:
            from terry.core.task_manager import TaskManager
            tm = TaskManager()
            if tm.load() and tm.is_active():
                prog = tm.progress_str()
                if prog:
                    current = tm.get_next_ready()
                    detail = current.description[:60] if current else ""
                    sys.stderr.write(f"\n\r\033[K  {prog}  {detail}\033[F")
        except Exception:
            pass

        sys.stderr.flush()

    # ── Helpers ────────────────────────────────────────────────────

    def _resolve_category(self, s: dict) -> str:
        """Determine the current phase category from state.

        Priority: finishing/done > active tool > default thinking.
        """
        # Finishing state takes precedence over everything
        if s.get("_finishing"):
            return "finishing"
        tool_name = str(s.get("tool_name", ""))
        if tool_name in ("grep", "glob", "find_tool", "web_search", "web_fetch"):
            return "searching"
        if tool_name in ("read_file", "ls", "ls_tool"):
            return "reading"
        if tool_name in ("write_file", "edit_file", "notebook", "todo_write", "notes"):
            return "writing"
        if tool_name == "bash":
            return "running"
        return "thinking"

    def _build_verb(self, category: str, s: dict, iteration: int, elapsed: float) -> str:
        """Pick a verb appropriate to the current context."""
        if category == "finishing":
            return _pick(_VERBS["finishing"], self._verb_idx)
        if category == "thinking":
            if iteration > 1:
                return _pick(_VERBS["deep"], self._verb_idx)
            return _pick(_VERBS["thinking"], self._verb_idx)
        pool = _VERBS.get(category, _VERBS["thinking"])
        return _pick(pool, self._verb_idx)


def version_callback(value: bool):
    """Print version and exit."""
    if value:
        print(f"Terry v{__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    config: str = typer.Option(None, "--config", "-c", help="Config file path"),
    model: str = typer.Option(None, "--model", "-m", help="Model name override"),
    api_key: str = typer.Option(
        None, "--api-key", "-k",
        help="API key override (⚠️  prefer env var: keys in CLI args are visible to other users via ps)",
    ),
    language: str = typer.Option(None, "--language", "-l", help="Language (en, zh)"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug logging"),
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True,
        help="Show version and exit",
    ),
):
    """Start Terry in interactive mode."""
    if ctx.invoked_subcommand is not None:
        return

    # Initialize i18n
    i18n = get_i18n()
    if language:
        if not i18n.set_language(language):
            console.print(f"[yellow]Unsupported language: {language}. Using {i18n.get_language()}[/yellow]")

    # Load environment
    load_dotenv(override=True)

    # Load config
    cfg = TerryConfig.load(config)
    if model:
        cfg.model.model = model
    if api_key:
        cfg.model.api_key = api_key
        console.print("[yellow]⚠️  API key passed via --api-key is visible in process lists (ps aux). Prefer env vars.[/yellow]")

    # Check API key
    if not cfg.model.api_key:
        env_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if env_key:
            cfg.model.api_key = env_key
        else:
            console.print(Panel(
                f"[yellow]{t('errors.api_key_missing', provider='ANTHROPIC')}[/yellow]\n\n"
                "Set it via:\n"
                "  • Environment: [dim]export ANTHROPIC_API_KEY=sk-...[/dim]\n"
                "  • Config file: [dim]terry.json[/dim] with [dim]model.api_key[/dim]\n"
                "  • CLI flag: [dim]terry --api-key sk-...[/dim]",
                title="⚙️  Configuration Required",
                border_style="yellow",
            ))
            raise typer.Exit(1)

    # Create agent
    workdir = Path.cwd()
    agent = Agent(config=cfg, workdir=workdir)

    # First-run wizard
    if FirstRunWizard.is_first_run():
        console.print(Panel(
            FirstRunWizard.get_welcome(),
            title="🚀 Welcome to Terry!",
            border_style="green",
        ))
        FirstRunWizard.mark_complete()
    else:
        tip = TipsEngine.get_random_tip()
        if tip:
            console.print(f"\033[90m{tip}\033[0m")

    # Show startup banner
    mode_str = agent.get_mode()
    mode_colors = {"deny": "red", "ask": "yellow", "auto": "green"}
    mode_color = mode_colors.get(mode_str, "white")
    console.print(Panel(
        f"[bold green]{t('app.name')} v{__version__}[/bold green]\n"
        f"[dim]{t('app.tagline')}[/dim]\n\n"
        f"{t('cli.model_info', provider=cfg.model.provider, model=cfg.model.model)}\n"
        f"Sandbox mode: [{mode_color}]{mode_str}[/{mode_color}] (Shift+Tab to cycle)\n"
        f"{t('cli.language_info', language=i18n.get_language().upper())}\n"
        f"{t('cli.tools_info', tools=', '.join(tool.name for tool in agent.tools.list_tools()))}\n"
        f"{t('cli.workdir_info', workdir=str(workdir))}",
        title=f"🚀 {t('app.name')}",
        border_style="green",
    ))

    # REPL loop
    run_repl(agent)


def run_repl(agent: Agent):
    """Interactive REPL loop with mode indicator and Shift+Tab support."""
    get_i18n()

    # Setup readline for command history and Shift+Tab mode cycling
    history_file = None
    if _readline_available:
        history_dir = get_terry_dir()
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / ".repl_history"
        try:
            readline.read_history_file(str(history_file))
        except (FileNotFoundError, OSError):
            pass
        readline.set_history_length(1000)
        atexit.register(lambda: readline.write_history_file(str(history_file)))

    # Dynamic tab completion from CommandRegistry (no hardcoded list)
    if _readline_available:
        def _get_commands():
            try:
                from terry.cli_commands import cli_registry
                cmds = set()
                for cmd_name in cli_registry._commands:
                    cmds.add(cmd_name)
                return sorted(cmds)
            except Exception:
                return ["/help", "/exit", "/new", "/model", "/tools", "/context",
                        "/mode", "/doctor", "/effort", "/goal", "/plan", "/config",
                        "/tasks", "/agents", "/save", "/load", "/undo", "/checkpoints"]

        def completer(text, state):
            options = [c for c in _get_commands() if c.startswith(text)]
            if state < len(options):
                return options[state]
            return None
        readline.set_completer(completer)
        readline.parse_and_bind("tab: complete")

    console.print(f"[dim]{t('cli.help_hint')} (Tab to complete commands)[/dim]\n")

    while True:
        mode_str = agent.get_mode()
        # Colored mode label
        mode_colors = {"deny": "red", "ask": "yellow", "auto": "green"}
        mode_colors.get(mode_str, "white")

        try:
            prompt = f"\033[36mterry [{mode_str}] ▸ \033[0m"
            user_input = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            console.print(f"\n[dim]{t('cli.goodbye')}[/dim]")
            break

        if not user_input:
            continue

        # Handle commands
        if user_input.startswith("/"):
            if handle_command(user_input, agent):
                continue
            else:
                break

        # Run agent
        console.rule("[bold]Agent[/bold]", style="dim")
        progress = ProgressDisplay()
        try:
            progress.start()
            response = agent.run(user_input, on_progress=progress.update)
            console.print(Panel(Markdown(response), border_style="dim"))
            console.rule(style="dim")
        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted[/dim]")
        except Exception as e:
            console.print(f"[red]{t('cli.error')}: {e}[/red]")
        finally:
            progress.stop()


def handle_command(cmd: str, agent: Agent) -> bool:
    """Handle slash commands via CommandRegistry. Returns True to continue, False to exit."""
    from .cli_commands import cli_registry
    result = cli_registry.dispatch(cmd, agent)
    if result is None:
        # Unknown command
        console.print(f"[dim]{t('errors.unknown_command', command=cmd)}. Type /help[/dim]")
        return True
    return result

@app.command("run")
def run_cmd(
    config: str = typer.Option(None, "--config", "-c", help="Config file path"),
    model: str = typer.Option(None, "--model", "-m", help="Model name override"),
    api_key: str = typer.Option(
        None, "--api-key", "-k",
        help="API key override (⚠️  prefer env var: keys in CLI args are visible to other users via ps)",
    ),
    language: str = typer.Option(None, "--language", "-l", help="Language (en, zh)"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug logging"),
):
    """Start Terry in interactive mode (explicit)."""
    # Create a fake context for the callback
    from typer.models import Context
    ctx = Context(command=run_cmd, info_name="run", parent=None)
    main_callback(ctx, config=config, model=model, api_key=api_key,
                  language=language, debug=debug, version=None)


@app.command("webui")
def webui_cmd(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind address"),
    port: int = typer.Option(8670, "--port", "-p", help="Listen port"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser"),
):
    """Start the Terry WebUI server."""
    from .webui.server import WebUIServer

    # Create agent factory
    def agent_factory():
        cfg = TerryConfig.load()
        cfg.model.api_key = cfg.model.api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""  # noqa: E501
        return Agent(config=cfg)

    server = WebUIServer(agent_factory=agent_factory, host=host, port=port)
    server.start()

    if not no_browser:
        import webbrowser
        webbrowser.open(f"http://{host}:{port}")

    console.print(f"\n[dim]WebUI: http://{host}:{port}[/dim]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
        console.print("[dim]WebUI stopped[/dim]")


@app.command("desktop")
def desktop_cmd(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind address"),
    port: int = typer.Option(8670, "--port", "-p", help="Listen port"),
    no_tray: bool = typer.Option(False, "--no-tray", help="Disable system tray icon"),
    browser_only: bool = typer.Option(False, "--browser", help="Browser only, no tray"),
):
    """Start Terry in desktop mode (system tray + WebUI)."""
    from .desktop import start_browser_only, start_system_tray

    def agent_factory():
        cfg = TerryConfig.load()
        cfg.model.api_key = cfg.model.api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""  # noqa: E501
        return Agent(config=cfg)

    if browser_only or no_tray:
        start_browser_only(host=host, port=port)
    else:
        start_system_tray(agent_factory=agent_factory, host=host, port=port)


@app.command("swe-bench")
def swe_bench_cmd(
    difficulty: str = typer.Option(None, "--difficulty", "-d", help="Filter by difficulty (easy/medium/hard)"),
    output: str = typer.Option(None, "--output", "-o", help="Output directory for reports"),
):
    """Run SWE-bench evaluation and generate score report."""
    from pathlib import Path

    from .core.swe_bench import SWEBenchRunner

    def agent_factory():
        cfg = TerryConfig.load()
        cfg.model.api_key = cfg.model.api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""  # noqa: E501
        return Agent(config=cfg, enable_subagents=False, enable_skills=False,
                     enable_memory=False, enable_session=False, enable_metrics=True,
                     enable_cache=False, enable_checkpoint=False, enable_planner=False)

    runner = SWEBenchRunner(
        agent_factory=agent_factory,
        output_dir=Path(output) if output else None,
    )

    report = runner.run_all(difficulty=difficulty)
    console.print("\n[bold]SWE-bench Report:[/bold]")
    console.print(f"  Total: {report['total']}, Passed: {report['passed']}, Failed: {report['failed']}")
    console.print(f"  Pass Rate: {report['pass_rate']}")
    console.print(f"  Avg Score: {report['avg_score']}")
    console.print(f"  Total Time: {report['total_time_s']}s")
    console.print(f"  Total Cost: ${report['total_cost_usd']}")


@app.command("init")
def init_cmd(path: str = typer.Argument(".", help="Project path")):
    """Initialize a Terry config file."""
    config_path = Path(path) / "terry.json"
    if config_path.exists():
        console.print(f"[yellow]Config already exists: {config_path}[/yellow]")
        return

    cfg = TerryConfig()
    cfg.save(str(config_path))
    console.print(f"[green]Created config: {config_path}[/green]")


@app.command("mcp")
def mcp_cmd(
    action: str = typer.Argument("list", help="Action: list, add, remove, test, discover"),
    name: str = typer.Argument("", help="Server name"),
    command: str = typer.Option("", "--command", "-c", help="Server command"),
    url: str = typer.Option("", "--url", "-u", help="Server URL (for remote MCP)"),
):
    """Manage MCP servers — add, list, test, remove without editing JSON."""
    from terry.mcp_config import McpConfigManager, McpServerConfig, discover_mcp_json

    mgr = McpConfigManager()

    if action == "list":
        servers = mgr.list_servers()
        if servers:
            console.print(f"\n[bold]MCP Servers ({len(servers)}):[/bold]")
            for s in servers:
                src = s.command or s.url or "unconfigured"
                console.print(f"  🔌 [bold]{s.name}[/bold] → {src[:60]}")
        else:
            console.print("[dim]No MCP servers configured.[/dim]")
            console.print("[dim]Try: terry mcp discover[/dim]")

    elif action == "add":
        if not name:
            console.print("[yellow]Usage: terry mcp add <name> --command '...'[/yellow]")
            return
        if not command and not url:
            console.print("[yellow]Need --command or --url[/yellow]")
            return
        config = McpServerConfig(
            name=name,
            command=command,
            url=url,
            args=command.split()[1:] if command else [],
        )
        mgr.add_server(config)
        console.print(f"[green]✅ Added MCP server: {name}[/green]")

    elif action == "remove":
        if not name:
            console.print("[yellow]Usage: terry mcp remove <name>[/yellow]")
            return
        mgr.remove_server(name)
        console.print(f"[green]✅ Removed MCP server: {name}[/green]")

    elif action == "test":
        if not name:
            console.print("[yellow]Usage: terry mcp test <name>[/yellow]")
            return
        console.print(f"Testing {name}...")
        result = mgr.test_server(name)
        status_color = {"ok": "green", "error": "red", "warning": "yellow", "timeout": "yellow"}
        color = status_color.get(result["status"], "dim")
        console.print(f"  [{color}]{result['status']}[/{color}]: {result['message']}")

    elif action == "discover":
        discovered = discover_mcp_json()
        if discovered:
            servers = discovered.get("mcpServers", discovered.get("servers", {}))
            if isinstance(servers, dict):
                console.print(f"\n[bold]Found {len(servers)} MCP server(s) in project:[/bold]")
                for name, cfg in servers.items():
                    if isinstance(cfg, dict):
                        src = cfg.get("command", cfg.get("url", "?"))
                        console.print(f"  📄 [bold]{name}[/bold] → {str(src)[:60]}")
                        # Option to auto-import
                        mgr.add_server(McpServerConfig.from_dict({"name": name, **cfg}))
                console.print("[green]✅ Imported to Terry config[/green]")
            else:
                console.print("[dim]No MCP servers found in project config[/dim]")
        else:
            console.print("[dim]No .mcp.json or mcp.json found in this directory[/dim]")

    else:
        console.print(f"[red]Unknown action: {action}. Use: list, add, remove, test, discover[/red]")


@app.command("login")
def login_cmd(
    provider: str = typer.Option("anthropic", "--provider", "-p", help="OAuth provider (anthropic, moonshot)"),
):
    """Log in to an AI provider via OAuth device flow (no API key needed)."""
    from terry.oauth import login
    success = login(provider)
    if not success:
        raise typer.Exit(1)


@app.command("logout")
def logout_cmd(
    provider: str = typer.Option("anthropic", "--provider", "-p", help="OAuth provider"),
):
    """Log out from an AI provider (remove stored OAuth token)."""
    from terry.oauth import logout
    logout(provider)


@app.command("profile")
def profile_cmd(
    action: str = typer.Argument("list", help="Action: list, use, create"),
    name: str = typer.Argument("", help="Profile name"),
):
    """Manage agent profiles — switch roles (coder, reviewer, architect, debugger, devops)."""
    from terry.profile import ProfileManager, BUILTIN_PROFILES

    pm = ProfileManager()

    if action == "list":
        profiles = pm.list_all()
        console.print(f"\n[bold]Available profiles ({len(profiles)}):[/bold]")
        for p in profiles:
            builtin = "🔧" if p.name in BUILTIN_PROFILES else "👤"
            active = " [green]◀ active[/green]" if pm._active_profile == p.name else ""
            console.print(
                f"  {builtin} [bold]{p.name:12s}[/bold] — {p.description[:60]}{active}"
            )

    elif action == "use":
        if not name:
            console.print("[yellow]Usage: terry profile use <name>[/yellow]")
            return
        try:
            profile = pm.use(name)
            console.print(f"[green]✅ Now using profile: {profile.name}[/green]")
            console.print(f"   {profile.description}")
            console.print(f"   Effort: {profile.effort} | Model: {profile.model_override or 'default'}")
        except ValueError as e:
            console.print(f"[red]❌ {e}[/red]")

    else:
        console.print(f"[red]Unknown action: {action}. Use: list, use[/red]")


@app.command("plugin")
def plugin_cmd(
    action: str = typer.Argument("list", help="Action: search, install, list, uninstall"),
    query: str = typer.Argument("", help="Search query or plugin name"),
):
    """Manage Terry plugins — search, install, list, or uninstall."""
    from terry.plugin_market import (
        PluginRegistry,
        search_plugins,
        install_plugin,
    )

    registry = PluginRegistry()

    if action == "list":
        installed = registry.list_installed()
        if installed:
            console.print(f"\n[bold]Installed plugins ({len(installed)}):[/bold]")
            for p in installed:
                trust_color = {"verified": "green", "community": "yellow", "unknown": "dim"}
                tc = trust_color.get(p.trust_level.value, "dim")
                console.print(f"  [{tc}]●[/{tc}] {p.name} v{p.version} — {p.description[:60]}")
        else:
            console.print("[dim]No plugins installed. Try: terry plugin search <query>[/dim]")

    elif action == "search":
        if not query:
            console.print("[yellow]Usage: terry plugin search <query>[/yellow]")
            return
        results = search_plugins(query)
        if results:
            console.print(f"\n[bold]Found {len(results)} plugin(s) for '{query}':[/bold]")
            for p in results[:20]:
                trust_icon = {"verified": "🔒", "community": "👥", "unknown": "❓"}
                icon = trust_icon.get(p.trust_level.value, "❓")
                console.print(
                    f"  {icon} [bold]{p.name}[/bold] v{p.version} "
                    f"[dim]({p.kind.value}, ★{p.rating:.1f}, {p.downloads}↓)[/dim]"
                )
                if p.description:
                    console.print(f"      {p.description[:100]}")
        else:
            console.print(f"[dim]No plugins found for '{query}'[/dim]")

    elif action == "install":
        if not query:
            console.print("[yellow]Usage: terry plugin install <name>[/yellow]")
            return
        try:
            manifest = install_plugin(query, registry)
            console.print(f"[green]✅ Installed {manifest.name} v{manifest.version}[/green]")
        except ValueError as e:
            console.print(f"[red]❌ {e}[/red]")

    elif action == "uninstall":
        if not query:
            console.print("[yellow]Usage: terry plugin uninstall <name>[/yellow]")
            return
        registry.uninstall(query)
        console.print(f"[green]✅ Uninstalled {query}[/green]")

    else:
        console.print(f"[red]Unknown action: {action}. Use: search, install, list, uninstall[/red]")


@app.command("acp")
def acp_cmd():
    """Start Terry in ACP mode (Agent Client Protocol for editor integration).

    Use this to connect Zed, JetBrains, or any ACP-compatible editor to Terry.
    The editor drives the agent session over stdio JSON-RPC.
    """
    from terry.acp import run_acp
    run_acp()


@app.command("tui")
def tui_cmd():
    """Start Terry with the Textual TUI (modern terminal interface)."""
    try:
        from terry.tui.app import run_tui
        cfg = TerryConfig.load()
        cfg.model.api_key = cfg.model.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        from terry.core.agent import Agent
        agent = Agent(config=cfg)
        run_tui(agent=agent)
    except ImportError:
        console.print("[red]Textual is not installed. Run: pip install textual[/red]")
        console.print("[dim]Falling back to REPL mode. Use 'terry' for the classic interface.[/dim]")


if __name__ == "__main__":
    app()
