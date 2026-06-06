"""CLI command handlers — extracted from cli.py, registered via CommandRegistry."""

from __future__ import annotations

from typing import Any

from rich.console import Console
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

def _cmd_exit(cmd: str, args: str | None, agent: Any) -> bool:
    console.print(f"[dim]{t('cli.goodbye')}[/dim]")
    return False


def _cmd_help(cmd: str, args: str | None, agent: Any) -> bool:
    console.print(Panel(
        f"[bold]{t('commands.help.description')}[/bold]\n\n"
        f"/help       - {t('commands.help.description')}\n"
        f"/exit       - {t('commands.quit.description')}\n"
        f"/new        - {t('commands.reset.description')}\n"
        f"/model      - Show current model\n"
        f"/mode       - Cycle sandbox mode (deny ↔ ask ↔ auto)\n"
        f"/mode <m>   - Set mode to deny, ask, or auto\n"
        f"/tools      - List available tools\n"
        f"/context    - Show context usage\n"
        f"/language   - {t('commands.language.description')}\n"
        f"/save       - {t('commands.save.description')}\n"
        f"/load       - {t('commands.load.description')}\n\n"
        f"[bold]Skills[/bold]\n"
        f"/skills /activate /deactivate /reload-skills\n\n"
        f"[bold]Safety[/bold]\n"
        f"/undo /checkpoints /plan /config /permissions\n\n"
        f"[bold]Workflow[/bold]\n"
        f"/wfd /auto /workflow /benchmark\n\n"
        f"[bold]Search[/bold]\n"
        f"/search /replay /fork /stream",
        title="Help",
    ))
    return True


def _cmd_new(cmd: str, args: str | None, agent: Any) -> bool:
    agent.reset()
    console.print(f"[dim]{t('status.conversation_reset')}[/dim]")
    return True


def _cmd_model(cmd: str, args: str | None, agent: Any) -> bool:
    console.print(f"Current model: {agent.config.model.provider}/{agent.config.model.model}")
    return True


def _cmd_tools(cmd: str, args: str | None, agent: Any) -> bool:
    tools = agent.tools.list_tools()
    if tools:
        console.print("[bold]Available Tools:[/bold]")
        for tool in tools:
            console.print(f"  - {tool.name}: {tool.description}")
    return True


def _cmd_context(cmd: str, args: str | None, agent: Any) -> bool:
    console.print(f"Messages: {len(agent.messages)}, Tool calls: {agent.tool_call_count}/{agent.config.max_tool_calls}")
    return True


# ── Safety Commands ────────────────────────────────────────────────

def _cmd_mode(cmd: str, args: str | None, agent: Any) -> bool:
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
        console.print(f"[{mode_color}]Mode: {new_mode}[/{mode_color}]")
    return True


def _cmd_permissions(cmd: str, args: str | None, agent: Any) -> bool:
    rules = agent.permission_store.list_rules()
    if rules:
        console.print("[bold]Permission Rules:[/bold]")
        for r in rules:
            action_color = {"allow": "green", "deny": "red", "ask": "yellow"}
            color = action_color.get(r["action"], "white")
            console.print(f"  [{color}]{r['action']:5s}[/{color}] {r['tool']:15s} [dim]({r['source']})[/dim]")
    console.print(f"Level: [bold]{agent.permission_level.value}[/bold]")
    return True


def _cmd_undo(cmd: str, args: str | None, agent: Any) -> bool:
    if agent.checkpoint_manager:
        last = agent.checkpoint_manager.get_last_checkpoint()
        if last:
            if agent.checkpoint_manager.restore(last["id"]):
                console.print(f"[green]Restored: {last['id']}[/green]")
            else:
                console.print("[red]Restore failed[/red]")
        else:
            console.print("[yellow]No checkpoints[/yellow]")
    return True


def _cmd_checkpoints(cmd: str, args: str | None, agent: Any) -> bool:
    if agent.checkpoint_manager:
        cps = agent.checkpoint_manager.list_checkpoints()
        if cps:
            console.print("[bold]Checkpoints:[/bold]")
            for cp in cps[:20]:
                console.print(f"  {cp['id']} ({cp.get('tag','')}) @ {cp.get('timestamp','')}")
    return True


# ── Plan & Config ──────────────────────────────────────────────────

def _cmd_plan(cmd: str, args: str | None, agent: Any) -> bool:
    if not args:
        console.print("[yellow]Usage: /plan <request>[/yellow]")
        return True
    if agent.planner:
        plan = agent.planner.create_plan(args, [t.name for t in agent.tools.list_tools()], str(agent.workdir))
        agent.plan = plan
        console.print(Panel(Markdown(agent.planner.format_plan(plan)), title="Plan", border_style="blue"))
    return True


def _cmd_config(cmd: str, args: str | None, agent: Any) -> bool:
    if args:
        kv = args.split("=", 1)
        if len(kv) == 2:
            key, value = kv[0].strip(), kv[1].strip()
            console.print(f"[green]Config updated: {key}={value}[/green]")
    else:
        import json
        console.print_json(json.dumps(agent.config._to_dict(), indent=2))
    return True


# ── Search & History ───────────────────────────────────────────────

def _cmd_search(cmd: str, args: str | None, agent: Any) -> bool:
    if args and agent.fts_search:
        results = agent.fts_search.search(args, limit=15)
        if results:
            for r in results:
                console.print(f"  {r['session_id'][:8]} [{r['role']}] {r['content'][:120]}")
        else:
            console.print("[yellow]No results[/yellow]")
    return True


def _cmd_replay(cmd: str, args: str | None, agent: Any) -> bool:
    if agent.fts_search:
        sessions = agent.fts_search.list_sessions(limit=10)
        for s in sessions:
            console.print(f"  {s['session_id'][:16]} ({s['message_count']} msgs)")
    return True


def _cmd_fork(cmd: str, args: str | None, agent: Any) -> bool:
    agent.fork()
    console.print("[green]Conversation forked[/green]")
    return True


def _cmd_stream(cmd: str, args: str | None, agent: Any) -> bool:
    if not args:
        console.print("[yellow]Usage: /stream <message>[/yellow]")
        return True
    for chunk in agent.llm.chat_stream(messages=agent.messages, system=agent.build_system_prompt()):
        console.print(chunk, end="")
    console.print()
    return True


# ── Workflow ───────────────────────────────────────────────────────

def _cmd_wfd(cmd: str, args: str | None, agent: Any) -> bool:
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


def _cmd_workflows(cmd: str, args: str | None, agent: Any) -> bool:
    cps = agent.dynamic_workflow.list_checkpoints()
    if cps:
        for cp in cps:
            console.print(f"  {cp['id']}: {cp['name'][:60]} [{cp['pattern']}]")
    return True


def _cmd_auto(cmd: str, args: str | None, agent: Any) -> bool:
    if args:
        tid = agent.autonomous_agent.submit_task(args)
        console.print(f"[green]Task: {tid}[/green]")
    else:
        s = agent.autonomous_agent.get_status()
        console.print(f"Queued: {s['queued']}, Active: {s['active']}, Done: {s['completed']}")
    return True


# ── Skills & Memory ────────────────────────────────────────────────

def _cmd_auto_skills(cmd: str, args: str | None, agent: Any) -> bool:
    skills = agent.skill_auto_creator.list_suggested_skills()
    if skills:
        for s in skills:
            console.print(f"  {s['name']}: confidence={s['confidence']:.0%}")
    return True


def _cmd_curator(cmd: str, args: str | None, agent: Any) -> bool:
    s = agent.skills_curator.get_cycle_summary()
    console.print(f"Tracked: {s['skills_tracked']}, Uses: {s['total_uses']}, Avg: {s['average_effectiveness']}")
    return True


def _cmd_tasks(cmd: str, args: str | None, agent: Any) -> bool:
    summary = agent.task_dag.get_summary()
    ready = agent.task_dag.get_next_ready(limit=5)
    console.print(f"Tasks: {summary}")
    for task in ready:
        console.print(f"  - {task.description[:80]}")
    return True


def _cmd_benchmark(cmd: str, args: str | None, agent: Any) -> bool:
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
    register_cli_command("/exit", _cmd_exit, "Exit Terry", "basic", ["/quit", "/q"])
    register_cli_command("/help", _cmd_help, "Show help", "basic")
    register_cli_command("/new", _cmd_new, "New conversation", "basic")
    register_cli_command("/model", _cmd_model, "Show model", "basic")
    register_cli_command("/tools", _cmd_tools, "List tools", "basic")
    register_cli_command("/context", _cmd_context, "Show context", "basic")

    register_cli_command("/mode", _cmd_mode, "Change mode", "safety")
    register_cli_command("/permissions", _cmd_permissions, "Show permissions", "safety")
    register_cli_command("/undo", _cmd_undo, "Undo change", "safety")
    register_cli_command("/checkpoints", _cmd_checkpoints, "List checkpoints", "safety")

    register_cli_command("/plan", _cmd_plan, "Plan task", "planning")
    register_cli_command("/config", _cmd_config, "Show/change config", "planning")

    register_cli_command("/search", _cmd_search, "Search history", "search")
    register_cli_command("/replay", _cmd_replay, "Replay session", "search")
    register_cli_command("/fork", _cmd_fork, "Fork conversation", "search")
    register_cli_command("/stream", _cmd_stream, "Stream response", "search")

    register_cli_command("/wfd", _cmd_wfd, "Dynamic workflow", "workflow")
    register_cli_command("/workflows", _cmd_workflows, "List workflows", "workflow")
    register_cli_command("/auto", _cmd_auto, "Autonomous task", "workflow")

    register_cli_command("/auto-skills", _cmd_auto_skills, "Auto skills", "skills")
    register_cli_command("/curator", _cmd_curator, "Skills curator", "skills")
    register_cli_command("/tasks", _cmd_tasks, "Task DAG", "skills")
    register_cli_command("/benchmark", _cmd_benchmark, "Run benchmark", "skills")


register_all_commands()
