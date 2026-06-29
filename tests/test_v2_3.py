"""Unit tests for v2.3.0: external editor integration."""

from __future__ import annotations


class TestEditor:
    def test_import(self):
        from terry.core.editor import detect_editor, open_in_editor, get_editor_info
        assert callable(detect_editor)
        assert callable(open_in_editor)
        assert callable(get_editor_info)

    def test_detect_editor(self):
        from terry.core.editor import detect_editor
        editor = detect_editor()
        assert isinstance(editor, str)
        assert len(editor) > 0

    def test_get_editor_info(self):
        from terry.core.editor import get_editor_info
        info = get_editor_info()
        assert "editor" in info
        assert "available" in info
        assert "visual" in info
        assert "editor_env" in info

    def test_build_command_vim(self):
        from terry.core.editor import _build_command
        cmd = _build_command("vim", "/tmp/test.py", 42)
        assert "+42" in cmd
        assert "/tmp/test.py" in cmd

    def test_build_command_code(self):
        from terry.core.editor import _build_command
        cmd = _build_command("code", "/tmp/test.py", 10)
        assert "--goto" in cmd

    def test_open_nonexistent_file(self):
        from terry.core.editor import open_in_editor
        result = open_in_editor("/tmp/nonexistent_12345.py")
        assert result is False

    def test_editor_slash_cmd(self):
        from terry.cli_commands import _cmd_editor_open
        from unittest.mock import MagicMock
        agent = MagicMock()
        result = _cmd_editor_open("/editor", None, agent)
        assert result is True
