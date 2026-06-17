"""Terry TUI — professional terminal interface powered by Textual.

Layout:
  ┌─────────────────────────────────────────────┐
  │ Terry vX.Y.Z  │ anthropic/sonnet  │ ask  1M │  ← Header
  ├──────────────────────┬──────────────────────┤
  │                      │  📋 Tasks            │
  │   Chat History       │  ✅ 1. Read code     │
  │                      │  🔄 2. Refactor      │
  │   > user: hi         │  ⬜ 3. Test          │
  │   🤖 Doing...        │                      │
  │                      │  📊 2.3K tokens      │
  ├──────────────────────┴──────────────────────┤
  │ ▸ /help  /plan  /doctor  Ctrl+O: focus     │  ← Footer
  └─────────────────────────────────────────────┘
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Footer, Header as TextualHeader, Input, Static

from terry.core.theme import TerryTheme


class ChatMessage(Static):
    """A single chat message bubble."""

    def __init__(self, role: str, content: str, timestamp: str = ""):
        self.role = role
        super().__init__(content)
        self.timestamp = timestamp or datetime.now().strftime("%H:%M")

    def render(self) -> str:
        prefix = "🤖" if self.role == "assistant" else "👤"
        color = TerryTheme.PRIMARY if self.role == "assistant" else TerryTheme.SECONDARY
        return f"[{color}]{prefix}[/{color}] [{TerryTheme.TEXT_MUTED}]{self.timestamp}[/] {self._content}"


class TaskPanel(Static):
    """Sidebar showing active plan progress."""

    tasks: reactive[list[dict[str, Any]]] = reactive([])

    def render(self) -> str:
        if not self.tasks:
            return f"[{TerryTheme.TEXT_MUTED}]No active plan[/]"

        lines = [f"[bold {TerryTheme.PRIMARY}]Active Plan[/]"]
        icons = {"pending": "⬜", "in_progress": "🔄", "completed": "✅",
                 "failed": "❌", "blocked": "🔒"}
        for t in self.tasks:
            icon = icons.get(t.get("status", "pending"), "❓")
            desc = t.get("description", "")[:40]
            lines.append(f"  {icon} {desc}")
        return "\n".join(lines)


class StatusLine(Static):
    """Status bar showing token count, cost, and progress."""

    tokens: reactive[int] = reactive(0)
    cost: reactive[float] = reactive(0.0)
    progress: reactive[str] = reactive("")

    def render(self) -> str:
        parts = []
        if self.tokens:
            parts.append(f"[bold]{self.tokens:,}[/] tok")
        if self.cost:
            parts.append(f"${self.cost:.4f}")
        if self.progress:
            parts.append(self.progress)
        text = "  │  ".join(parts) if parts else f"[{TerryTheme.TEXT_MUTED}]Ready[/]"
        return f"[{TerryTheme.SECONDARY}]{text}[/{TerryTheme.SECONDARY}]"


class TerryTUI(App):
    """Terry Textual TUI application."""

    CSS = f"""
    Screen {{
        background: {TerryTheme.BG};
    }}
    #header {{
        dock: top;
        height: 1;
        background: {TerryTheme.SURFACE};
        color: {TerryTheme.TEXT_PRIMARY};
        padding: 0 1;
    }}
    #chat {{
        border-right: solid {TerryTheme.BORDER};
    }}
    #sidebar {{
        width: 28;
        border-left: solid {TerryTheme.BORDER};
        padding: 1;
        background: {TerryTheme.BG};
    }}
    #status-bar {{
        dock: bottom;
        height: 1;
        background: {TerryTheme.SURFACE};
        padding: 0 1;
    }}
    #input-area {{
        dock: bottom;
        height: 3;
        background: {TerryTheme.SURFACE};
        border-top: solid {TerryTheme.BORDER};
        padding: 0 1;
    }}
    ChatMessage {{
        padding: 0 1;
        margin: 0;
    }}
    TaskPanel {{
        height: auto;
    }}
    StatusLine {{
        height: 1;
    }}
    """

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+o", "toggle_focus", "Focus"),
        ("j", "scroll_down", "Scroll Down"),
        ("k", "scroll_up", "Scroll Up"),
        ("g", "scroll_home", "Top"),
        ("shift+g", "scroll_end", "Bottom"),
    ]

    def __init__(self, agent: Any = None):
        super().__init__()
        self.agent = agent
        self._messages: list[dict] = []

    def compose(self) -> ComposeResult:
        """Build the TUI layout."""
        # Header
        yield Static(
            f"[bold {TerryTheme.PRIMARY}]Terry v0.9.0[/] │ "
            f"[{TerryTheme.TEXT_SECONDARY}]Ctrl+O focus │ /help │ /plan[/]",
            id="header",
        )

        # Status bar
        yield StatusLine(id="status-bar")

        # Main content area
        with Horizontal():
            with VerticalScroll(id="chat"):
                yield Static(f"[{TerryTheme.TEXT_MUTED}]Welcome! Type a message or /help to begin.[/]", id="welcome")
            with Vertical(id="sidebar"):
                yield TaskPanel(id="tasks")
                yield Static(f"[{TerryTheme.TEXT_MUTED}]📊 0 tokens[/]", id="stats")

        # Input area
        with Container(id="input-area"):
            yield Input(placeholder="Type a message or /command...", id="user-input")

        # Footer with key bindings
        yield Footer()

    def on_mount(self) -> None:
        """Focus the input on startup."""
        self.query_one("#user-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input submission."""
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""

        # Add user message to chat
        chat = self.query_one("#chat", VerticalScroll)
        chat.mount(ChatMessage("user", text))

        # Simulate agent response (placeholder)
        if self.agent:
            try:
                response = self.agent.run(text)
                chat.mount(ChatMessage("assistant", response[:500]))
            except Exception as e:
                chat.mount(ChatMessage("assistant", f"[red]Error: {e}[/red]"))
        else:
            chat.mount(ChatMessage("assistant", f"[{TerryTheme.TEXT_MUTED}]Agent not connected. Start with: terry tui[/]"))

        # Remove welcome message
        welcome = chat.query_one("#welcome", Static)
        if welcome:
            welcome.remove()

        chat.scroll_end(animate=False)

    def action_toggle_focus(self) -> None:
        """Toggle between chat and sidebar focus."""
        pass  # TODO: Implement focus toggle

    def action_scroll_down(self) -> None:
        self.query_one("#chat", VerticalScroll).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#chat", VerticalScroll).scroll_up()

    def action_scroll_home(self) -> None:
        self.query_one("#chat", VerticalScroll).scroll_home()

    def action_scroll_end(self) -> None:
        self.query_one("#chat", VerticalScroll).scroll_end()


def run_tui(agent: Any = None) -> None:
    """Entry point: launch the Terry TUI."""
    app = TerryTUI(agent=agent)
    app.run()
