"""Terry Design System — unified color palette, spacing, and typography.

Defines the visual identity used across CLI, Textual TUI, and WebUI.
Single source of truth for all visual constants — no ad-hoc colors.

Usage:
    from terry.core.theme import TerryTheme
    console.print(f"[{TerryTheme.PRIMARY}]Terry[/{TerryTheme.PRIMARY}]")
"""

from __future__ import annotations


class TerryTheme:
    """Unified color palette and design tokens.

    Colors are defined as 24-bit hex values for maximum precision.
    Semantic naming ensures consistency across all surfaces.
    """

    # ── Background ─────────────────────────────────────────────────
    BG = "#0f0f1a"           # 深邃黑蓝 — 主背景
    SURFACE = "#1a1a2e"      # 卡片/面板背景
    ELEVATED = "#16213e"     # 悬浮层/对话框
    BORDER = "#2a2a4a"       # 边框/分割线

    # ── Accent ─────────────────────────────────────────────────────
    PRIMARY = "#7c3aed"      # 紫色 — 主色调
    PRIMARY_HOVER = "#8b5cf6"
    SECONDARY = "#06b6d4"    # 青色 — 辅色调
    SECONDARY_HOVER = "#22d3ee"

    # ── Semantic ───────────────────────────────────────────────────
    SUCCESS = "#10b981"      # 绿色 — 成功/完成
    WARNING = "#f59e0b"      # 黄色 — 警告
    DANGER = "#ef4444"       # 红色 — 错误/危险
    INFO = "#3b82f6"         # 蓝色 — 信息

    # ── Text ───────────────────────────────────────────────────────
    TEXT_PRIMARY = "#e2e8f0"
    TEXT_SECONDARY = "#94a3b8"
    TEXT_MUTED = "#64748b"

    # ── Status (Rich-compatible named colors) ──────────────────────
    STATUS_COLORS: dict[str, str] = {
        "completed": "green",
        "running": "yellow",
        "failed": "red",
        "cancelled": "dim",
        "pending": "white",
        "blocked": "yellow",
        "in_progress": "yellow",
    }

    # ── Rich border styles ─────────────────────────────────────────
    BORDER_STYLE = "bright_black"
    PANEL_BORDER_DEFAULT = "bright_black"
    PANEL_BORDER_SUCCESS = "green"
    PANEL_BORDER_WARNING = "yellow"

    # ── Typography ─────────────────────────────────────────────────
    FONT_MONO = "monospace"
    FONT_UI = "system-ui, sans-serif"

    # ── Spacing (characters) ───────────────────────────────────────
    PAD_X = 2
    PAD_Y = 1

    # ── Animation ──────────────────────────────────────────────────
    SPINNER_INTERVAL = 3.0   # 动词轮换间隔（秒）
    FPS = 10                 # ProgressDisplay 刷新率

    # ── Component presets ──────────────────────────────────────────
    @classmethod
    def table_style(cls) -> dict:
        """Default Rich Table styling."""
        return {
            "border_style": cls.BORDER_STYLE,
            "title_style": f"bold {cls.PRIMARY.replace('#', '')}",
            "header_style": "bold cyan",
        }

    @classmethod
    def panel_success(cls) -> dict:
        return {"border_style": cls.PANEL_BORDER_SUCCESS, "padding": (cls.PAD_Y, cls.PAD_X)}

    @classmethod
    def panel_default(cls) -> dict:
        return {"border_style": cls.PANEL_BORDER_DEFAULT, "padding": (cls.PAD_Y, cls.PAD_X)}
