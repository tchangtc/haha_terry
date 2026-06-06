"""CLI entry point for Terry."""

from __future__ import annotations

import atexit
import os
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from . import __version__
from .core.config import TerryConfig
from .core.agent import Agent
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
    i18n = get_i18n()

    # Setup readline for command history and Shift+Tab mode cycling
    history_file = None
    if _readline_available:
        history_dir = Path.home() / ".terry"
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / ".repl_history"
        try:
            readline.read_history_file(str(history_file))
        except (FileNotFoundError, OSError):
            pass
        readline.set_history_length(1000)
        atexit.register(lambda: readline.write_history_file(str(history_file)))

    console.print(f"[dim]{t('cli.help_hint')}[/dim]\n")

    while True:
        mode_str = agent.get_mode()
        # Colored mode label
        mode_colors = {"deny": "red", "ask": "yellow", "auto": "green"}
        mode_color = mode_colors.get(mode_str, "white")
        mode_label = f"[{mode_color}]{mode_str}[/{mode_color}]"

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
    """Handle slash commands. Returns True to continue, False to exit."""
    i18n = get_i18n()
    parts = cmd.split(maxsplit=1)
    command = parts[0].lower()

    if command in ("/exit", "/quit", "/q"):
        console.print(f"[dim]{t('cli.goodbye')}[/dim]")
        return False

    elif command == "/help":
        console.print(Panel(
            f"[bold]{t('commands.help.description')}[/bold]\n\n"
            f"/help     - {t('commands.help.description')}\n"
            f"/exit     - {t('commands.quit.description')}\n"
            f"/new      - {t('commands.reset.description')}\n"
            f"/model    - Show current model\n"
            f"/mode     - Cycle sandbox mode (deny ↔ ask ↔ auto)\n"
            f"/mode <m> - Set mode to deny, ask, or auto\n"
            f"/tools    - {t('tools.bash.description')}\n"
            f"/context  - Show context usage\n"
            f"/language - {t('commands.language.description')}\n"
            f"/save     - {t('commands.save.description')}\n"
            f"/load     - {t('commands.load.description')}\n\n"
            f"[bold]Skill Commands[/bold]\n"
            f"/skills          - List all available skills\n"
            f"/skill <name>    - Show skill details\n"
            f"/activate <name> - Manually activate a skill\n"
            f"/deactivate      - Deactivate current skill\n"
            f"/reload-skills   - Reload skills from disk",
            title="Help",
        ))
        return True

    elif command == "/new":
        agent.reset()
        console.print(f"[dim]{t('status.conversation_reset')}[/dim]")
        return True

    elif command == "/model":
        console.print(f"Current model: {agent.config.model.provider}/{agent.config.model.model}")
        return True

    elif command == "/tools":
        tools = agent.tools.list_tools()
        if tools:
            console.print("[bold]Available Tools:[/bold]")
            for tool in tools:
                console.print(f"  - {tool.name}: {tool.description}")
        else:
            console.print("No tools available")
        return True

    elif command == "/context":
        msg_count = len(agent.messages)
        tool_count = agent.tool_call_count
        console.print(f"Messages: {msg_count}, Tool calls: {tool_count}/{agent.config.max_tool_calls}")
        return True

    elif command == "/mode":
        if len(parts) > 1:
            new_mode = parts[1].strip().lower()
            if agent.set_mode(new_mode):
                mode_color = {"deny": "red", "ask": "yellow", "auto": "green"}.get(new_mode, "white")
                console.print(f"[{mode_color}]Mode changed to: {new_mode}[/{mode_color}]")
            else:
                console.print(f"[red]Invalid mode: {new_mode}. Use: deny, ask, auto[/red]")
        else:
            # No argument: cycle to next mode
            new_mode = agent.cycle_mode()
            mode_color = {"deny": "red", "ask": "yellow", "auto": "green"}.get(new_mode, "white")
            console.print(f"[{mode_color}]Mode: {new_mode} (cycle with Shift+Tab in permission prompts)[/{mode_color}]")
        return True

    elif command == "/language":
        if len(parts) > 1:
            new_lang = parts[1].strip().lower()
            if i18n.set_language(new_lang):
                console.print(f"[green]{t('status.language_changed', language=new_lang.upper())}[/green]")
            else:
                console.print(f"[yellow]Unsupported language: {new_lang}. Supported: {', '.join(i18n.get_supported_languages())}[/yellow]")
        else:
            console.print(f"Current language: {i18n.get_language().upper()}")
            console.print(f"Supported languages: {', '.join(i18n.get_supported_languages())}")
            console.print(f"Usage: /language <{'|'.join(i18n.get_supported_languages())}>")
        return True

    elif command == "/save":
        filename = parts[1].strip() if len(parts) > 1 else None
        if agent.session:
            path = agent.save_session(filename)
            console.print(f"[green]{t('status.session_saved', filename=path)}[/green]")
        else:
            console.print("[yellow]Session management not available[/yellow]")
        return True

    elif command == "/load":
        if len(parts) > 1:
            filename = parts[1].strip()
            if agent.session:
                if agent.load_session(filename):
                    console.print(f"[green]{t('status.session_loaded', filename=filename)}[/green]")
                else:
                    console.print(f"[red]Failed to load session: {filename}[/red]")
            else:
                console.print("[yellow]Session management not available[/yellow]")
        else:
            console.print(f"[yellow]{t('commands.load.usage')}[/yellow]")
        return True

    # Skill commands
    elif command == "/skills":
        skills = agent.list_skills()
        if skills:
            console.print("[bold]Available Skills:[/bold]")
            for skill in skills:
                status = " [green](active)[/green]" if skill.get('active') else ""
                console.print(f"  - [bold]{skill['name']}[/bold]{status}: {skill['description']}")
        else:
            console.print("[yellow]No skills available[/yellow]")
        return True

    elif command == "/skill":
        if len(parts) > 1:
            skill_name = parts[1].strip()
            skill_info = agent.get_skill_info(skill_name)
            if skill_info:
                status = " [green](active)[/green]" if skill_info.get('active') else ""
                console.print(Panel(
                    f"[bold]{skill_info['name']}[/bold]{status}\n\n"
                    f"{skill_info['description']}\n\n"
                    f"[dim]Content preview:[/dim]\n{skill_info['content'][:200]}...",
                    title="Skill Details",
                    border_style="blue",
                ))
            else:
                console.print(f"[red]Skill not found: {skill_name}[/red]")
        else:
            console.print("[yellow]Usage: /skill <skill_name>[/yellow]")
        return True

    elif command == "/activate":
        if len(parts) > 1:
            skill_name = parts[1].strip()
            if agent.activate_skill(skill_name):
                console.print(f"[green]Skill activated: {skill_name}[/green]")
            else:
                console.print(f"[red]Failed to activate skill: {skill_name}[/red]")
        else:
            console.print("[yellow]Usage: /activate <skill_name>[/yellow]")
        return True

    elif command == "/deactivate":
        agent.deactivate_skill()
        console.print("[green]Skill deactivated[/green]")
        return True

    elif command == "/reload-skills":
        count = agent.reload_skills()
        console.print(f"[green]Reloaded {count} skills[/green]")
        return True

    else:
        console.print(f"[dim]{t('errors.unknown_command', command=command)}. Type /help for available commands[/dim]")
        return True


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
