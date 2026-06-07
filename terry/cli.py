"""CLI entry point for Terry."""

from __future__ import annotations

import atexit
import os
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
    api_key: str = typer.Option(None, "--api-key", "-k", help="API key override"),
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

    # Setup tab completion for commands
    commands_list = [
        "/help", "/exit", "/new", "/model", "/mode", "/tools", "/context",
        "/language", "/save", "/load", "/skills", "/skill", "/activate",
        "/deactivate", "/reload-skills", "/undo", "/checkpoints", "/plan",
        "/config", "/permissions", "/fork", "/stream", "/repomap", "/search",
        "/benchmark", "/replay", "/workflow", "/curator", "/tasks",
    ]
    if _readline_available:
        def completer(text, state):
            options = [c for c in commands_list if c.startswith(text)]
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
        try:
            console.print(f"[dim]{t('cli.thinking')}[/dim]")
            response = agent.run(user_input)
            console.print(Panel(Markdown(response), border_style="dim"))
            console.rule(style="dim")
        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted[/dim]")
        except Exception as e:
            console.print(f"[red]{t('cli.error')}: {e}[/red]")


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
    api_key: str = typer.Option(None, "--api-key", "-k", help="API key override"),
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


if __name__ == "__main__":
    app()
