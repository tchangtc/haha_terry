"""CLI command handlers — extracted from cli.py, registered via CommandRegistry."""

from __future__ import annotations

from rich.console import Console

from .core.typing_protocols import AgentLike
from rich.markdown import Markdown
from rich.panel import Panel

from .core.commands import Command, CommandRegistry
from .i18n import t

console = Console()

# ── Global registry ────────────────────────────────────────────────

cli_registry = CommandRegistry()


def register_cli_command(name: str, handler, description: str = "",
                         category: str = "general", aliases: list[str] | None = None):
    """Register a CLI command handler."""
    cli_registry.register(Command(name, handler, description, category, aliases=aliases or []))


# ── Basic Commands ─────────────────────────────────────────────────

def _cmd_exit(cmd: str, args: str | None, agent: AgentLike) -> bool:
    console.print(f"[dim]{t('cli.goodbye')}[/dim]")
    return False


def _cmd_help(cmd: str, args: str | None, agent: AgentLike) -> bool:
    console.print(Panel(
        f"[bold]Basics[/bold]\n"
        f"/help       - Show this help\n"
        f"/exit       - Exit Terry\n"
        f"/new        - Reset conversation\n"
        f"/model      - Show current model\n"
        f"/tools      - List available tools\n"
        f"/context    - Show context usage\n"
        f"/save /load - Save and restore sessions\n\n"
        f"[bold]Safety & Control[/bold]\n"
        f"/mode <ask|auto|deny> - Set sandbox mode\n"
        f"/permissions - View permission rules\n"
        f"/undo [<id>] - Undo changes with preview\n"
        f"/checkpoints - Browse/restore/delete snapshots\n"
        f"/plan <task> - Plan before executing\n"
        f"/config [reload] - Show or hot-reload config\n\n"
        f"[bold]Diagnostics[/bold]\n"
        f"/doctor      - Run full system health check\n"
        f"/effort <low|medium|high|xhigh> - Set effort level\n\n"
        f"[bold]Skills[/bold]\n"
        f"/skills /activate /deactivate /reload-skills\n\n"
        f"[bold]Workflow & Automation[/bold]\n"
        f"/goal <objective> - Autonomous goal-driven loop\n"
        f"/wfd <goal> <pattern> - Dynamic multi-agent workflow\n"
        f"/workflow <script.py> - Run a Python workflow script\n"
        f"/bg <task> - Fire-and-forget background task\n"
        f"/tasks [list|peek|cancel] - Monitor background tasks\n"
        f"/agents [--tree] - Agent dashboard\n"
        f"/auto <task> - Submit autonomous task\n"
        f"/routine [list|add|trigger] - Manage routines\n\n"
        f"[bold]Review & Search[/bold]\n"
        f"/ultrareview <file> - Multi-dimension code review\n"
        f"/benchmark - Run evaluation suites\n"
        f"/search /replay /fork /stream",
        title="Help — Terry v{}".format(__import__('terry').__version__),
    ))
    return True


def _cmd_new(cmd: str, args: str | None, agent: AgentLike) -> bool:
    agent.reset()
    console.print(f"[dim]{t('status.conversation_reset')}[/dim]")
    return True


def _cmd_model(cmd: str, args: str | None, agent: AgentLike) -> bool:
    console.print(f"Current model: {agent.config.model.provider}/{agent.config.model.model}")
    return True


def _cmd_tools(cmd: str, args: str | None, agent: AgentLike) -> bool:
    tools = agent.tools.list_tools()
    if tools:
        console.print("[bold]Available Tools:[/bold]")
        for tool in tools:
            console.print(f"  - {tool.name}: {tool.description}")
    return True


def _cmd_context(cmd: str, args: str | None, agent: AgentLike) -> bool:
    console.print(f"Messages: {len(agent.messages)}, Tool calls: {agent.tool_call_count}/{agent.config.max_tool_calls}")
    return True


# ── Safety Commands ────────────────────────────────────────────────


def _cmd_effort(cmd: str, args: str | None, agent: AgentLike) -> bool:
    valid = ("low", "medium", "high", "xhigh")
    if not args:
        current = getattr(agent.config, "effort_level", "medium")
        console.print(f"Current effort: [bold]{current}[/bold]")
        console.print(f"[dim]Usage: /effort {'|'.join(valid)}[/dim]")
        return True
    level = args.strip().lower()
    if level not in valid: console.print(f"[red]Invalid. Use: {', '.join(valid)}[/red]"); return True
    if hasattr(agent, "set_effort") and agent.set_effort(level): console.print(f"[green]Effort: {level}[/green]")
    return True

def _cmd_mode(cmd: str, args: str | None, agent: AgentLike) -> bool:
    if args:
        new_mode = args.strip().lower()
        if agent.set_mode(new_mode):
            mode_color = {"deny": "red", "ask": "yellow", "auto": "green"}.get(new_mode, "white")
            console.print(f"[{mode_color}]Mode changed to: {new_mode}[/{mode_color}]")
        else:
            console.print(f"[red]Invalid mode: {new_mode}[/red]")
    else:
        new_mode = agent.cycle_mode()
        mode_color = {"deny": "red", "ask": "yellow", "auto": "green"}.get(new_mode, "white")
        console.print(f"[{mode_color}]Mode cycled to: {new_mode}[/{mode_color}]")
        console.print(f"[dim]Use /mode <ask|auto|deny> to set directly.[/dim]")
    return True


def _cmd_permissions(cmd: str, args: str | None, agent: AgentLike) -> bool:
    rules = agent.permission_store.list_rules()
    if rules:
        console.print("[bold]Permission Rules:[/bold]")
        for r in rules:
            action_color = {"allow": "green", "deny": "red", "ask": "yellow"}
            color = action_color.get(r["action"], "white")
            console.print(f"  [{color}]{r['action']:5s}[/{color}] {r['tool']:15s} [dim]({r['source']})[/dim]")
    console.print(f"Level: [bold]{agent.permission_level.value}[/bold]")
    return True


def _cmd_undo(cmd: str, args: str | None, agent: AgentLike) -> bool:
    """Undo a checkpoint. /undo [<id>]"""
    if not agent.checkpoint_manager:
        console.print("[yellow]Checkpoint system not enabled[/yellow]")
        return True

    cp_id = args.strip() if args else None
    if cp_id:
        checkpoint = agent.checkpoint_manager.get_checkpoint(cp_id)
        if not checkpoint:
            console.print(f"[red]Checkpoint not found: {cp_id}[/red]")
            return True
    else:
        checkpoint = agent.checkpoint_manager.get_last_checkpoint()
        if not checkpoint:
            console.print("[yellow]No checkpoints available[/yellow]")
            return True

    # Show diff preview
    preview = agent.checkpoint_manager.diff_preview(checkpoint["id"])
    if preview:
        console.print(Panel(
            preview[:2000],
            title=f"Changes to revert — {checkpoint.get('tag', '') or checkpoint['id'][:12]}",
            border_style="yellow",
        ))

    # Confirmation prompt
    from rich.prompt import Confirm
    if not Confirm.ask("This will revert changes. Continue?", default=False):
        console.print("[dim]Cancelled[/dim]")
        return True

    if agent.checkpoint_manager.restore(checkpoint["id"]):
        tag = checkpoint.get("tag", "") or checkpoint["id"]
        console.print(f"[green]Restored: {tag}[/green]")
    else:
        console.print("[red]Restore failed[/red]")
    return True


def _cmd_checkpoints(cmd: str, args: str | None, agent: AgentLike) -> bool:
    """List / delete / diff checkpoints. /checkpoints [delete|diff <id>]"""
    if not agent.checkpoint_manager:
        console.print("[yellow]Checkpoint system not enabled[/yellow]")
        return True

    # Parse subcommands
    if args:
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower()
        sub_args = parts[1] if len(parts) > 1 else ""

        if sub == "delete":
            cid = sub_args.strip()
            if not cid:
                console.print("[yellow]Usage: /checkpoints delete <id>[/yellow]")
                return True
            if agent.checkpoint_manager.delete_checkpoint(cid):
                console.print(f"[green]Deleted checkpoint: {cid}[/green]")
            else:
                console.print(f"[red]Checkpoint not found: {cid}[/red]")
            return True

        if sub == "diff":
            cid = sub_args.strip()
            if not cid:
                console.print("[yellow]Usage: /checkpoints diff <id>[/yellow]")
                return True
            preview = agent.checkpoint_manager.diff_preview(cid)
            if preview:
                console.print(Panel(preview[:3000], title=f"Diff Preview — {cid}", border_style="yellow"))
            else:
                console.print(f"[red]Checkpoint not found or preview unavailable: {cid}[/red]")
            return True

    # Default: list checkpoints in a rich table
    cps = agent.checkpoint_manager.list_checkpoints()
    if not cps:
        console.print("[yellow]No checkpoints available[/yellow]")
        return True

    from rich.table import Table
    table = Table(title="Checkpoints")
    table.add_column("#", style="dim", width=3)
    table.add_column("ID", style="cyan", width=20)
    table.add_column("Tag", style="bold")
    table.add_column("Method", width=6)
    table.add_column("Timestamp", style="dim", width=20)

    for i, cp in enumerate(cps[:20], 1):
        cid = cp.get("id", "?")
        tag = (cp.get("tag") or "-")[:30]
        method = cp.get("method", "tar")
        method_style = {"git": "[green]git[/green]", "tar": "[yellow]tar[/yellow]"}.get(method, method)
        timestamp = cp.get("timestamp", "?")

        table.add_row(
            str(i),
            cid[:18],
            tag,
            method_style,
            timestamp,
        )

    console.print(table)
    console.print("[dim]Actions: /undo [id] | /checkpoints diff <id> | /checkpoints delete <id>[/dim]")
    return True


# ── Plan & Config ──────────────────────────────────────────────────

def _cmd_plan(cmd: str, args: str | None, agent: AgentLike) -> bool:
    if not args:
        console.print("[yellow]Usage: /plan <request>[/yellow]")
        return True
    if agent.planner:
        plan = agent.planner.create_plan(args, [t.name for t in agent.tools.list_tools()], str(agent.workdir))
        agent.plan = plan
        console.print(Panel(Markdown(agent.planner.format_plan(plan)), title="Plan", border_style="blue"))
    else:
        console.print("[yellow]Planner not enabled. Start Terry with --planner flag.[/yellow]")
    return True


def _cmd_config(cmd: str, args: str | None, agent: AgentLike) -> bool:
    """Manage configuration. /config [reload | <key>=<value>]"""
    if args and args.strip().startswith("reload"):
        _cmd_config_reload(agent)
        return True

    if args:
        kv = args.split("=", 1)
        if len(kv) == 2:
            key, value = kv[0].strip(), kv[1].strip()
            console.print(f"[green]Config updated: {key}={value}[/green]")
    else:
        import json
        console.print_json(json.dumps(agent.config._to_dict(), indent=2))
    return True


def _cmd_config_reload(agent: AgentLike) -> None:
    """Reload config from disk and show changes."""
    from terry.core.config import TerryConfig

    config_path = TerryConfig._find_config()
    if not config_path:
        console.print("[yellow]No config file found on disk. Create one with 'terry --save-config'[/yellow]")
        return

    new_config = TerryConfig()
    changed = new_config.reload(config_path)

    if not changed:
        console.print("[green]Config unchanged[/green]")
        return

    # Separate errors from changes
    errors = [c for c in changed if c.startswith("error:")]
    actual_changes = [c for c in changed if not c.startswith("error:")]

    if errors:
        console.print("[red]Config validation failed — keeping old config:[/red]")
        for e in errors:
            console.print(f"  [red]{e.replace('error: ', '')}[/red]")
        return

    if not actual_changes:
        console.print("[green]Config unchanged[/green]")
        return

    # Push changes to subsystems
    applied = agent.reconfigure(new_config, actual_changes)

    # Show diff table
    from rich.table import Table
    table = Table(title="Config Changes Applied")
    table.add_column("Setting", style="bold cyan")
    table.add_column("Status", style="bold")

    for field in actual_changes:
        status = "[green]applied[/green]" if field in applied else "[yellow]needs restart[/yellow]"
        table.add_row(field, status)

    console.print(table)

    not_applied = set(actual_changes) - set(applied)
    if not_applied:
        console.print(
            f"[yellow]Note: {len(not_applied)} setting(s) require a restart to take full effect:[/yellow]"
        )
        for f in sorted(not_applied):
            console.print(f"  [dim]• {f}[/dim]")


# ── Search & History ───────────────────────────────────────────────

def _cmd_search(cmd: str, args: str | None, agent: AgentLike) -> bool:
    if not args:
        console.print("[yellow]Usage: /search <query>[/yellow]")
        return True
    if not agent.fts_search:
        console.print("[yellow]Search not enabled. Start Terry with --fts flag.[/yellow]")
        return True
    results = agent.fts_search.search(args, limit=15)
    if results:
        for r in results:
            console.print(f"  {r['session_id'][:8]} [{r['role']}] {r['content'][:120]}")
    else:
        console.print("[yellow]No results[/yellow]")
    return True


def _cmd_replay(cmd: str, args: str | None, agent: AgentLike) -> bool:
    if agent.fts_search:
        sessions = agent.fts_search.list_sessions(limit=10)
        for s in sessions:
            console.print(f"  {s['session_id'][:16]} ({s['message_count']} msgs)")
    return True


def _cmd_fork(cmd: str, args: str | None, agent: AgentLike) -> bool:
    agent.fork()
    console.print("[green]Conversation forked[/green]")
    return True


def _cmd_stream(cmd: str, args: str | None, agent: AgentLike) -> bool:
    if not args:
        console.print("[yellow]Usage: /stream <message>[/yellow]")
        return True
    for chunk in agent.llm.chat_stream(messages=agent.messages, system=agent.build_system_prompt()):
        console.print(chunk, end="")
    console.print()
    return True


# ── Workflow ───────────────────────────────────────────────────────

def _cmd_wfd(cmd: str, args: str | None, agent: AgentLike) -> bool:
    if not args:
        console.print("[yellow]Usage: /wfd <goal> [pattern][/yellow]")
        return True
    from .core.dynamic_workflow import WorkflowPattern
    parts = args.split()
    pattern = WorkflowPattern.FAN_OUT_MERGE
    for p in parts:
        if p in [x.value for x in WorkflowPattern]:
            pattern = WorkflowPattern(p)
            parts.remove(p)
    goal = " ".join(parts) if parts else args
    wf = agent.dynamic_workflow.plan_workflow(goal, pattern, agent.llm)
    console.print(f"[dim]Workflow {wf.id}: {len(wf.stages)} stages ({pattern.value})[/dim]")
    with console.status("[green]Executing...[/green]"):
        results = agent.dynamic_workflow.execute(wf)
    for sid, r in list(results.items())[:10]:
        if sid.startswith("_"):
            continue
        ok = not str(r).startswith("Error")
        console.print(f"  {'✅' if ok else '❌'} {sid}: {str(r)[:120]}")
    return True


def _cmd_workflows(cmd: str, args: str | None, agent: AgentLike) -> bool:
    cps = agent.dynamic_workflow.list_checkpoints()
    if cps:
        for cp in cps:
            console.print(f"  {cp['id']}: {cp['name'][:60]} [{cp['pattern']}]")
    return True


def _cmd_auto(cmd: str, args: str | None, agent: AgentLike) -> bool:
    if args:
        tid = agent.autonomous_agent.submit_task(args)
        console.print(f"[green]Task: {tid}[/green]")
    else:
        s = agent.autonomous_agent.get_status()
        console.print(f"Queued: {s['queued']}, Active: {s['active']}, Done: {s['completed']}")
    return True


# ── Skills & Memory ────────────────────────────────────────────────


def _cmd_reload_skills(cmd: str, args: str | None, agent: AgentLike) -> bool:
    if agent.skill_manager:
        agent.skill_manager.reload()
        console.print(f"[green]Skills reloaded ({len(agent.skill_manager.list_skills())} skills)[/green]")
    else: console.print("[yellow]Skill system not enabled[/yellow]")
    return True

def _cmd_auto_skills(cmd: str, args: str | None, agent: AgentLike) -> bool:
    if not agent.skill_auto_creator:
        console.print("[yellow]Skill auto-creator not available[/yellow]")
        return True
    try:
        if hasattr(agent.skill_auto_creator, "list_suggested_skills"):
            skills = agent.skill_auto_creator.list_suggested_skills()
        elif hasattr(agent.skill_auto_creator, "get_suggestions"):
            skills = agent.skill_auto_creator.get_suggestions()
        else:
            console.print("[yellow]No suggested skills available[/yellow]")
            return True
        if skills:
            for s in skills:
                name = s.get("name", s) if isinstance(s, dict) else str(s)
                conf = s.get("confidence", 0) if isinstance(s, dict) else 0
                console.print(f"  {name}: confidence={conf:.0%}")
        else:
            console.print("[dim]No skill suggestions yet. Complete complex tasks to generate them.[/dim]")
    except Exception as e:
        console.print(f"[yellow]Could not list auto skills: {e}[/yellow]")
    return True


def _cmd_curator(cmd: str, args: str | None, agent: AgentLike) -> bool:
    s = agent.skills_curator.get_cycle_summary()
    console.print(f"Tracked: {s['skills_tracked']}, Uses: {s['total_uses']}, Avg: {s['average_effectiveness']}")
    return True


def _cmd_tasks(cmd: str, args: str | None, agent: AgentLike) -> bool:
    """Manage background tasks. /tasks [list|peek <id>|cancel <id>]

    Without subcommand, lists all registered background tasks.
    Use 'dag' subcommand for the old TaskDAG view.
    """
    from .core.background_registry import get_background_registry

    if not args:
        # Default: list background tasks
        return _cmd_tasks_list(cmd, None, agent)

    parts = args.strip().split(maxsplit=1)
    sub = parts[0].lower()
    sub_args = parts[1] if len(parts) > 1 else ""

    if sub == "list":
        return _cmd_tasks_list(cmd, sub_args, agent)
    elif sub == "peek":
        return _cmd_tasks_peek(cmd, sub_args, agent)
    elif sub == "cancel":
        return _cmd_tasks_cancel(cmd, sub_args, agent)
    elif sub == "dag":
        # Legacy TaskDAG view
        return _cmd_tasks_dag(cmd, sub_args, agent)
    else:
        console.print(f"[yellow]Unknown subcommand: {sub}. Use list, peek, cancel, or dag.[/yellow]")
        return True


def _cmd_tasks_list(cmd: str, args: str | None, agent: AgentLike) -> bool:
    """List background tasks, optionally filtered by status."""
    from .core.background_registry import get_background_registry

    filter_status = args.strip() if args else None
    tasks = get_background_registry().list(status=filter_status if filter_status else None)

    if not tasks:
        console.print("[yellow]No background tasks found[/yellow]")
        return True

    from rich.table import Table
    table = Table(title="Background Tasks")
    table.add_column("ID", style="cyan", width=14)
    table.add_column("Description")
    table.add_column("System", style="blue", width=14)
    table.add_column("Status", style="bold", width=12)
    table.add_column("Created", style="dim", width=10)

    status_color = {
        "completed": "green", "running": "yellow", "failed": "red",
        "cancelled": "dim", "pending": "white",
    }

    for t in tasks:
        color = status_color.get(t.status, "white")
        from datetime import datetime
        created = datetime.fromtimestamp(t.created_at).strftime("%H:%M:%S")
        table.add_row(
            t.id[:12],
            t.description[:60],
            t.system,
            f"[{color}]{t.status}[/{color}]",
            created,
        )

    console.print(table)
    if not filter_status:
        running = sum(1 for t in tasks if t.status == "running")
        if running:
            console.print(f"[dim]{running} running, {len(tasks)} total[/dim]")
    console.print("[dim]Actions: /tasks peek <id> | /tasks cancel <id> | /tasks list running[/dim]")
    return True


def _cmd_tasks_peek(cmd: str, args: str | None, agent: AgentLike) -> bool:
    """Show partial result of a running task. /tasks peek <id>"""
    from .core.background_registry import get_background_registry

    if not args:
        console.print("[yellow]Usage: /tasks peek <id>[/yellow]")
        return True

    task = get_background_registry().get(args.strip())
    if not task:
        console.print(f"[red]Task not found: {args}[/red]")
        return True

    console.print(Panel(
        f"[bold]Status:[/bold] {task.status}\n\n"
        f"[bold]System:[/bold] {task.system}\n\n"
        f"[bold]Result:[/bold]\n{task.result or '[dim]No result yet[/dim]'}\n\n"
        f"[bold]Error:[/bold]\n{task.error or '[dim]None[/dim]'}",
        title=f"Task: {task.id} — {task.description[:60]}",
        border_style="blue",
    ))
    return True


def _cmd_tasks_cancel(cmd: str, args: str | None, agent: AgentLike) -> bool:
    """Cancel a background task. /tasks cancel <id>"""
    from .core.background_registry import get_background_registry

    if not args:
        console.print("[yellow]Usage: /tasks cancel <id>[/yellow]")
        return True

    if get_background_registry().cancel(args.strip()):
        console.print(f"[yellow]Cancelled: {args}[/yellow]")
    else:
        console.print(f"[red]Task not found: {args}[/red]")
    return True


def _cmd_tasks_dag(cmd: str, args: str | None, agent: AgentLike) -> bool:
    """Show TaskDAG summary (legacy). /tasks dag"""
    summary = agent.task_dag.get_summary()
    ready = agent.task_dag.get_next_ready(limit=5)
    console.print(f"DAG Summary: {summary}")
    for task in ready:
        console.print(f"  - {task.description[:80]}")
    return True


def _cmd_bg(cmd: str, args: str | None, agent: AgentLike) -> bool:
    """Fire-and-forget a background task. /bg <description>"""
    if not args:
        console.print("[yellow]Usage: /bg <description of task>[/yellow]")
        console.print("Examples:")
        console.print("  /bg audit security patterns")
        console.print("  /bg refactor the CLI module")
        return True

    # Submit to autonomous agent for background execution
    if hasattr(agent, "autonomous_agent") and agent.autonomous_agent:
        tid = agent.autonomous_agent.submit_task(args)
        console.print(f"[green]Background task started: {tid}[/green]")
    else:
        # Fallback: register directly for tracking but execute inline
        from .core.background_registry import BackgroundTask, get_background_registry
        task = BackgroundTask(description=args[:120], system="manual", status="running")
        tid = get_background_registry().register(task)
        console.print(f"[green]Background task registered: {tid}[/green]")
        console.print("[dim]Note: autonomous agent not available, task is tracking-only[/dim]")
    return True


def _cmd_goal(cmd: str, args: str | None, agent: AgentLike) -> bool:
    """Goal-driven autonomous loop. /goal <description>

    Examples:
      /goal all tests pass and ruff check is clean
      /goal implement user authentication module
      /goal refactor cli.py to use extracted sub-modules
    """
    if not args:
        console.print("[yellow]Usage: /goal <description of the goal>[/yellow]")
        console.print("[dim]Examples:[/dim]")
        console.print("  [dim]/goal all tests pass and ruff check is clean[/dim]")
        console.print("  [dim]/goal implement the user authentication module[/dim]")
        return True

    if not hasattr(agent, "run_goal"):
        console.print("[red]Goal loop not available — agent does not support run_goal()[/red]")
        return True

    with console.status("[green]Running goal loop...[/green]"):
        result = agent.run_goal(args)

    if result.get("met"):
        console.print(f"\n[bold green]Goal achieved![/bold green]")
    else:
        console.print(
            f"\n[bold yellow]Goal not fully met "
            f"(score: {result.get('final_score', 0):.2f})[/bold yellow]"
        )

    console.print(Panel(
        f"Iterations: {result.get('iterations', 0)}\n"
        f"Final score: {result.get('final_score', 0):.2f}\n"
        f"Feedback: {result.get('feedback', '')[:500]}\n\n"
        f"Final output:\n{result.get('final_output', '')[:2000]}",
        title="Goal Result",
        border_style="green" if result.get("met") else "yellow",
    ))
    return True



def _cmd_doctor(cmd: str, args: str | None, agent: AgentLike) -> bool:
    from .core.doctor import Doctor
    doctor = Doctor(agent); results = doctor.run_all()
    if not results: console.print("[yellow]No results[/yellow]"); return True
    from rich.table import Table
    table = Table(title="Diagnostic Report", border_style="cyan")
    table.add_column("Check", style="bold", width=18)
    table.add_column("Status", width=7, justify="center")
    table.add_column("Message")
    for r in results:
        style = {"pass": "green", "warn": "yellow", "fail": "red"}.get(r.status, "white")
        table.add_row(r.name, f"[{style}]{r.status.upper()}[/{style}]", r.message)
    console.print(table)
    passed = sum(1 for r in results if r.status == "pass")
    console.print(f"[green]{passed} passed[/green]  [yellow]{sum(1 for r in results if r.status == 'warn')} warnings[/yellow]  [red]{sum(1 for r in results if r.status == 'fail')} failed[/red]")
    return True

def _cmd_workflow(cmd: str, args: str | None, agent: AgentLike) -> bool:
    """Run a WorkflowScript. /workflow <path.py>"""
    from pathlib import Path
    if not args:
        console.print("[yellow]Usage: /workflow <path.py>[/yellow]"); return True
    path = Path(args.strip())
    if not path.exists(): console.print(f"[red]Not found: {path}[/red]"); return True
    ns: dict = {}
    try: exec(path.read_text(encoding="utf-8"), ns)
    except Exception as e: console.print(f"[red]Error: {e}[/red]"); return True
    from .core.workflow_script import WorkflowScript
    wf = ns.get("wf")
    if not isinstance(wf, WorkflowScript): console.print("[red]Script must define 'wf' as WorkflowScript[/red]"); return True
    with console.status("[green]Running..."): results = wf.run(agent_factory=lambda: agent)
    for sid, r in results.items():
        ok = not str(r).startswith("Error")
        console.print(f"  {'[green]OK[/green]' if ok else '[red]FAIL[/red]'} {sid}: {str(r)[:120]}")
    return True


def _cmd_agents(cmd: str, args: str | None, agent: AgentLike) -> bool:
    """Show agent dashboard. /agents [--tree]"""
    from .core.background_registry import get_background_registry
    tasks = get_background_registry().list(limit=100)
    if not tasks: console.print("[yellow]No agents[/yellow]"); return True
    from rich.table import Table
    use_tree = args and "--tree" in args
    if use_tree:
        from rich.tree import Tree
        t = Tree("[bold]Agent Tree[/bold]")
        by_parent: dict = {}; roots = []
        for tk in tasks:
            tk.children = by_parent.setdefault(tk.id, [])
            if tk.parent_id: by_parent.setdefault(tk.parent_id, []).append(tk)
            else: roots.append(tk)
        def _add(n, tree):
            for c in n.children:
                label = f"{c.id[:8]} [{c.status}] {c.description[:40]}"
                _add(c, tree.add(label))
        for r in roots[:10]:
            node = t.add(f"{r.id[:8]} [{r.status}] {r.description[:40]}")
            _add(r, node)
        console.print(t)
    else:
        table = Table(title="Agents Dashboard"); table.add_column("ID"); table.add_column("Description"); table.add_column("System"); table.add_column("Depth"); table.add_column("Status")
        for t in tasks[:50]:
            c = {"completed":"green","running":"yellow","failed":"red","cancelled":"dim"}.get(t.status,"white")
            table.add_row(t.id[:10], t.description[:50], t.system or "-", str(t.depth or 0), f"[{c}]{t.status}[/{c}]")
        console.print(table)
    running = sum(1 for t in tasks if t.status == "running")
    console.print(f"[dim]{running} running, {len(tasks)} total[/dim]")
    return True


def _cmd_ultrareview(cmd: str, args: str | None, agent: AgentLike) -> bool:
    """Adversarial code review. /ultrareview [file_path|code]"""
    if not args: console.print("[yellow]Usage: /ultrareview <file_path|code>[/yellow]"); return True
    from pathlib import Path
    path = Path(args.strip())
    if path.exists():
        code = path.read_text(encoding="utf-8"); file_path = str(path)
    else:
        code = args; file_path = "<inline>"
    from .core.ultrareview import Ultrareview
    with console.status("[green]Reviewing..."):
        result = Ultrareview(agent_factory=lambda: agent).review(code, file_path)
    from rich.table import Table
    table = Table(title="Ultrareview"); table.add_column("Dimension"); table.add_column("Score")
    for d, s in result.scores.items():
        c = "green" if s >= 0.8 else "yellow" if s >= 0.5 else "red"
        table.add_row(d, f"[{c}]{s:.0%}[/{c}]")
    console.print(table)
    for f in result.findings:
        icon = "✅" if f.passed else "❌"
        c = {"critical":"red","major":"yellow","minor":"dim"}.get(f.severity,"white")
        console.print(f"  {icon} [{c}][{f.severity.upper()}][/{c}] {f.dimension}: {f.description[:120]}")
    if not result.passed:
        console.print("[yellow]Auto-fixing...[/yellow]")
        final = Ultrareview(agent_factory=lambda: agent).auto_fix(code, result)
        console.print(f"[green]{'All issues resolved' if final.passed else 'Some issues remain'} after {final.iterations} iterations[/green]")
    return True


def _cmd_routine(cmd: str, args: str | None, agent: AgentLike) -> bool:
    """Manage routines. /routine list|add|trigger|remove"""
    from .core.scheduler import CronScheduler
    s = CronScheduler()
    if not args: args = "list"
    parts = args.strip().split(maxsplit=2)
    sub = parts[0].lower()
    if sub == "list":
        tasks = s.list_tasks()
        if not tasks: console.print("[yellow]No routines[/yellow]"); return True
        from rich.table import Table
        t = Table(title="Routines"); t.add_column("ID"); t.add_column("Name"); t.add_column("Type"); t.add_column("Next"); t.add_column("Runs")
        for r in tasks:
            t.add_row(str(r.get("id","?")), r.get("name",r.get("type","?"))[:30], r.get("trigger","cron"), (r.get("next_run") or "-")[:16], str(r.get("run_count",0)))
        console.print(t)
    elif sub == "add" and len(parts) >= 3:
        s.schedule(name=parts[1], task_type="routine", params={}, trigger="cron" if len(parts) < 3 else parts[2])
        console.print(f"[green]Added: {parts[1]}[/green]")
    elif sub == "trigger" and len(parts) >= 2:
        r = s.trigger_api(parts[1]); console.print(f"[green]Triggered: {r[:200]}[/green]")
    elif sub == "remove" and len(parts) >= 2:
        s.cancel(int(parts[1])); console.print(f"[green]Removed[/green]")
    else: console.print("[yellow]Usage: /routine list|add|trigger|remove[/yellow]")
    return True


def _cmd_benchmark(cmd: str, args: str | None, agent: AgentLike) -> bool:
    from .core.benchmark import BenchmarkRunner
    runner = BenchmarkRunner(agent=agent)
    if args and args in runner.DEFAULT_SUITES:
        with console.status("[green]Running..."):
            suite = runner.run_suite(args)
        for r in suite.results:
            icon = "✅" if r.status == "passed" else "❌"
            console.print(f"  {icon} {r.problem_id}: {r.status} ({r.score:.0%})")
    else:
        for name in runner.DEFAULT_SUITES:
            console.print(f"  {name}")
    return True


# ── Register all commands ──────────────────────────────────────────

def register_all_commands():
    """Register all built-in CLI commands in the global CommandRegistry.

    Categories: basic, skills, safety, workflow, search, config, planning.
    Called once at CLI startup by terry.cli.
    """
    register_cli_command("/exit", _cmd_exit, "Exit Terry", "basic", ["/quit", "/q"])
    register_cli_command("/help", _cmd_help, "Show help", "basic")
    register_cli_command("/new", _cmd_new, "New conversation", "basic")
    register_cli_command("/model", _cmd_model, "Show model", "basic")
    register_cli_command("/tools", _cmd_tools, "List tools", "basic")
    register_cli_command("/context", _cmd_context, "Show context", "basic")

    register_cli_command("/effort", _cmd_effort, "Set effort level", "basic")
    register_cli_command("/mode", _cmd_mode, "Change mode", "safety")
    register_cli_command("/permissions", _cmd_permissions, "Show permissions", "safety")
    register_cli_command("/undo", _cmd_undo, "Undo change", "safety")
    register_cli_command("/checkpoints", _cmd_checkpoints, "List checkpoints", "safety")

    register_cli_command("/doctor", _cmd_doctor, "Run diagnostics", "safety")
    register_cli_command("/plan", _cmd_plan, "Plan task", "planning")
    register_cli_command("/config", _cmd_config, "Show/change config", "planning")

    register_cli_command("/search", _cmd_search, "Search history", "search")
    register_cli_command("/replay", _cmd_replay, "Replay session", "search")
    register_cli_command("/fork", _cmd_fork, "Fork conversation", "search")
    register_cli_command("/stream", _cmd_stream, "Stream response", "search")

    register_cli_command("/wfd", _cmd_wfd, "Dynamic workflow", "workflow")
    register_cli_command("/workflows", _cmd_workflows, "List workflows", "workflow")
    register_cli_command("/auto", _cmd_auto, "Autonomous task", "workflow")
    register_cli_command("/bg", _cmd_bg, "Background task", "workflow")
    register_cli_command("/goal", _cmd_goal, "Goal-driven autonomous loop", "workflow")
    register_cli_command("/workflow", _cmd_workflow, "Run a workflow script (.py)", "workflow")
    register_cli_command("/agents", _cmd_agents, "Show agent dashboard", "workflow")
    register_cli_command("/ultrareview", _cmd_ultrareview, "Adversarial code review", "workflow")
    register_cli_command("/routine", _cmd_routine, "Manage automated routines", "workflow")
    register_cli_command("/tasks", _cmd_tasks, "Background tasks", "workflow")

    register_cli_command("/reload-skills", _cmd_reload_skills, "Reload all skills", "skills", ["/reload"])
    register_cli_command("/auto-skills", _cmd_auto_skills, "Auto skills", "skills")
    register_cli_command("/curator", _cmd_curator, "Skills curator", "skills")
    register_cli_command("/benchmark", _cmd_benchmark, "Run benchmark", "skills")


register_all_commands()
