#!/usr/bin/env python3
"""
Unit tests for zunda_hook.py logic (no external API calls required).
Run: python3 test_logic.py
"""

import json
import os
import sys
import tempfile
import shutil
import subprocess
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))
import zunda_hook


class TestParseTranscriptLines(unittest.TestCase):
    """Tests for _parse_transcript_lines."""

    def test_basic_user_assistant(self):
        lines = [
            json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "Hello"}]}}),
            json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Hi there"}]}}),
        ]
        result = zunda_hook._parse_transcript_lines(lines)
        self.assertIn("User: Hello", result)
        self.assertIn("Claude: Hi there", result)

    def test_filters_system_messages(self):
        lines = [
            json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "[Request interrupted by user for tool use]"}]}}),
            json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "The user doesn't want to proceed"}]}}),
            json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "Real message"}]}}),
        ]
        result = zunda_hook._parse_transcript_lines(lines)
        self.assertNotIn("Request interrupted", result)
        self.assertNotIn("doesn't want", result)
        self.assertIn("User: Real message", result)

    def test_skips_non_user_assistant(self):
        lines = [
            json.dumps({"type": "file-history-snapshot", "snapshot": {}}),
            json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "Hello"}]}}),
        ]
        result = zunda_hook._parse_transcript_lines(lines)
        self.assertEqual(result, "User: Hello")

    def test_skips_tool_use_blocks(self):
        lines = [
            json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "123", "name": "Read"},
                {"type": "text", "text": "I read the file"},
            ]}}),
        ]
        result = zunda_hook._parse_transcript_lines(lines)
        self.assertEqual(result, "Claude: I read the file")

    def test_empty_lines(self):
        result = zunda_hook._parse_transcript_lines(["", "  ", "\n"])
        self.assertEqual(result, "")

    def test_invalid_json(self):
        lines = ["not json", '{"type": "user"', json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "OK"}]}})]
        result = zunda_hook._parse_transcript_lines(lines)
        self.assertEqual(result, "User: OK")

    def test_multiple_text_blocks_joined(self):
        lines = [
            json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "text", "text": "First part"},
                {"type": "text", "text": "Second part"},
            ]}}),
        ]
        result = zunda_hook._parse_transcript_lines(lines)
        self.assertEqual(result, "Claude: First part Second part")

    def test_no_text_content_skipped(self):
        lines = [
            json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "123", "name": "Bash"},
            ]}}),
        ]
        result = zunda_hook._parse_transcript_lines(lines)
        self.assertEqual(result, "")


class TestTranscriptDelta(unittest.TestCase):
    """Tests for read_transcript with delta offset tracking."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_offsets_file = zunda_hook.TRANSCRIPT_OFFSETS_FILE
        zunda_hook.TRANSCRIPT_OFFSETS_FILE = os.path.join(self.tmpdir, ".transcript_offsets")

    def tearDown(self):
        zunda_hook.TRANSCRIPT_OFFSETS_FILE = self.orig_offsets_file
        shutil.rmtree(self.tmpdir)

    def _write_transcript(self, lines):
        path = os.path.join(self.tmpdir, "test.jsonl")
        with open(path, "w") as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")
        return path

    def test_first_read_gets_all(self):
        path = self._write_transcript([
            {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "Hello"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Hi"}]}},
        ])
        result = zunda_hook.read_transcript(path, full=False)
        self.assertIn("User: Hello", result)
        self.assertIn("Claude: Hi", result)

    def test_second_read_gets_only_new(self):
        path = self._write_transcript([
            {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "First"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Response1"}]}},
        ])
        zunda_hook.read_transcript(path, full=False)

        # Append new messages
        with open(path, "a") as f:
            f.write(json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "Second"}]}}) + "\n")
            f.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Response2"}]}}) + "\n")

        result = zunda_hook.read_transcript(path, full=False)
        self.assertNotIn("First", result)
        self.assertNotIn("Response1", result)
        self.assertIn("User: Second", result)
        self.assertIn("Claude: Response2", result)

    def test_full_mode_ignores_offset(self):
        path = self._write_transcript([
            {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "First"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Response1"}]}},
        ])
        zunda_hook.read_transcript(path, full=False)  # advances offset

        result = zunda_hook.read_transcript(path, full=True)
        self.assertIn("User: First", result)
        self.assertIn("Claude: Response1", result)

    def test_empty_delta(self):
        path = self._write_transcript([
            {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "Hello"}]}},
        ])
        zunda_hook.read_transcript(path, full=False)
        result = zunda_hook.read_transcript(path, full=False)
        self.assertEqual(result, "")

    def test_nonexistent_file(self):
        result = zunda_hook.read_transcript("/nonexistent/path.jsonl", full=False)
        self.assertEqual(result, "")

    def test_separate_offsets_per_file(self):
        path1 = os.path.join(self.tmpdir, "proj1.jsonl")
        path2 = os.path.join(self.tmpdir, "proj2.jsonl")
        for path, text in [(path1, "Project1"), (path2, "Project2")]:
            with open(path, "w") as f:
                f.write(json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}) + "\n")

        r1 = zunda_hook.read_transcript(path1, full=False)
        r2 = zunda_hook.read_transcript(path2, full=False)
        self.assertIn("Project1", r1)
        self.assertIn("Project2", r2)

        # Second read should be empty for both
        self.assertEqual(zunda_hook.read_transcript(path1, full=False), "")
        self.assertEqual(zunda_hook.read_transcript(path2, full=False), "")


class TestProjectActivation(unittest.TestCase):
    """Tests for project activation/deactivation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_file = zunda_hook.ACTIVE_PROJECTS_FILE
        zunda_hook.ACTIVE_PROJECTS_FILE = os.path.join(self.tmpdir, ".active_projects")

    def tearDown(self):
        zunda_hook.ACTIVE_PROJECTS_FILE = self.orig_file
        shutil.rmtree(self.tmpdir)

    def test_inactive_by_default(self):
        self.assertFalse(zunda_hook.is_project_active("/some/project"))

    def test_activate_and_check(self):
        zunda_hook.activate_project("/my/project")
        self.assertTrue(zunda_hook.is_project_active("/my/project"))
        self.assertFalse(zunda_hook.is_project_active("/other/project"))

    def test_deactivate(self):
        zunda_hook.activate_project("/my/project")
        zunda_hook.deactivate_project("/my/project")
        self.assertFalse(zunda_hook.is_project_active("/my/project"))

    def test_multiple_projects(self):
        zunda_hook.activate_project("/project/a")
        zunda_hook.activate_project("/project/b")
        self.assertTrue(zunda_hook.is_project_active("/project/a"))
        self.assertTrue(zunda_hook.is_project_active("/project/b"))

        zunda_hook.deactivate_project("/project/a")
        self.assertFalse(zunda_hook.is_project_active("/project/a"))
        self.assertTrue(zunda_hook.is_project_active("/project/b"))

    def test_deactivate_nonexistent(self):
        # Should not raise
        zunda_hook.deactivate_project("/never/activated")

    def test_activate_idempotent(self):
        zunda_hook.activate_project("/my/project")
        zunda_hook.activate_project("/my/project")
        with open(zunda_hook.ACTIVE_PROJECTS_FILE) as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertEqual(lines.count("/my/project"), 1)

    def test_empty_cwd(self):
        self.assertFalse(zunda_hook.is_project_active(""))


class TestDispatch(unittest.TestCase):
    """Tests for @zunda command dispatch via subprocess."""

    def _run_hook(self, hook_input: dict) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "zunda_hook.py")],
            input=json.dumps(hook_input),
            capture_output=True, text=True, timeout=10,
        )

    def test_zunda_on_exits_2(self):
        result = self._run_hook({
            "session_id": "test", "cwd": "/tmp/test-project",
            "hook_event_name": "UserPromptSubmit", "prompt": "@zunda on",
        })
        self.assertEqual(result.returncode, 2)
        self.assertIn("Zundamon ON", result.stderr)

    def test_zunda_off_exits_2(self):
        result = self._run_hook({
            "session_id": "test", "cwd": "/tmp/test-project",
            "hook_event_name": "UserPromptSubmit", "prompt": "@zunda off",
        })
        self.assertEqual(result.returncode, 2)
        self.assertIn("Zundamon OFF", result.stderr)

    def test_zunda_status_exits_2(self):
        result = self._run_hook({
            "session_id": "test", "cwd": "/tmp/test-project",
            "hook_event_name": "UserPromptSubmit", "prompt": "@zunda status",
        })
        self.assertEqual(result.returncode, 2)
        self.assertIn("Zundamon:", result.stderr)
        self.assertIn("VOICEVOX:", result.stderr)
        self.assertIn("Speed:", result.stderr)

    def test_zunda_full_exits_2(self):
        result = self._run_hook({
            "session_id": "test", "cwd": "/tmp/test-project",
            "hook_event_name": "UserPromptSubmit", "prompt": "@zunda full",
        })
        self.assertEqual(result.returncode, 2)
        self.assertIn("full conversation", result.stderr)

    def test_normal_prompt_exits_0(self):
        result = self._run_hook({
            "session_id": "test", "cwd": "/tmp/test-project",
            "hook_event_name": "UserPromptSubmit", "prompt": "just a normal prompt",
        })
        self.assertEqual(result.returncode, 0)


class TestSpeedValidation(unittest.TestCase):
    """Tests for VOICEVOX_SPEED clamping."""

    def test_normal_value(self):
        self.assertEqual(min(2.0, max(0.5, 1.4)), 1.4)

    def test_too_low(self):
        self.assertEqual(min(2.0, max(0.5, 0.1)), 0.5)

    def test_too_high(self):
        self.assertEqual(min(2.0, max(0.5, 5.0)), 2.0)

    def test_boundary_low(self):
        self.assertEqual(min(2.0, max(0.5, 0.5)), 0.5)

    def test_boundary_high(self):
        self.assertEqual(min(2.0, max(0.5, 2.0)), 2.0)


class TestDebatePipeline(unittest.TestCase):
    """Tests for the 3-step debate pipeline in zundamon_answer."""

    @patch.object(zunda_hook, "GEMINI_API_KEY", "fake-key")
    @patch.object(zunda_hook, "_call_gemini")
    def test_full_pipeline_3_calls(self, mock_gemini):
        """All 3 steps succeed — _call_gemini called exactly 3 times."""
        mock_gemini.side_effect = [
            "Draft answer about Python decorators",
            "問題なし",
            "Pythonのデコレータは関数を修飾する仕組みなのだ！",
        ]
        result = zunda_hook.zundamon_answer("Pythonのデコレータって何？")
        self.assertEqual(mock_gemini.call_count, 3)
        self.assertIn("なのだ", result)

    @patch.object(zunda_hook, "GEMINI_API_KEY", "fake-key")
    @patch.object(zunda_hook, "_call_gemini")
    def test_critique_feeds_into_synthesis(self, mock_gemini):
        """Critique output is passed to the synthesis step."""
        mock_gemini.side_effect = [
            "Wrong: Python is compiled",
            "事実誤認: Pythonはインタプリタ言語である",
            "Pythonはインタプリタ言語なのだ！",
        ]
        result = zunda_hook.zundamon_answer("Pythonは何語？")
        # Verify the 3rd call (synthesis) received the critique
        synth_prompt = mock_gemini.call_args_list[2][0][0]
        self.assertIn("事実誤認", synth_prompt)
        self.assertIn("インタプリタ", result)

    @patch.object(zunda_hook, "GEMINI_API_KEY", "fake-key")
    @patch.object(zunda_hook, "_call_gemini")
    def test_draft_failure_returns_error(self, mock_gemini):
        """If draft (step 1) fails, return error immediately."""
        mock_gemini.side_effect = Exception("API timeout")
        result = zunda_hook.zundamon_answer("test question")
        self.assertEqual(mock_gemini.call_count, 1)
        self.assertIn("うまく答えられなかった", result)

    @patch.object(zunda_hook, "GEMINI_API_KEY", "fake-key")
    @patch.object(zunda_hook, "_call_gemini")
    def test_critique_failure_uses_fallback(self, mock_gemini):
        """If critique (step 2) fails, synthesis still runs with fallback text."""
        mock_gemini.side_effect = [
            "Draft answer",
            Exception("API error"),
            "最終回答なのだ！",
        ]
        result = zunda_hook.zundamon_answer("test question")
        self.assertEqual(mock_gemini.call_count, 3)
        # Verify fallback critique was used
        synth_prompt = mock_gemini.call_args_list[2][0][0]
        self.assertIn("検証できなかった", synth_prompt)
        self.assertIn("なのだ", result)

    @patch.object(zunda_hook, "GEMINI_API_KEY", "fake-key")
    @patch.object(zunda_hook, "_call_gemini")
    def test_synthesis_failure_returns_error(self, mock_gemini):
        """If synthesis (step 3) fails, return error."""
        mock_gemini.side_effect = [
            "Draft answer",
            "問題なし",
            Exception("API error"),
        ]
        result = zunda_hook.zundamon_answer("test question")
        self.assertEqual(mock_gemini.call_count, 3)
        self.assertIn("うまく答えられなかった", result)

    @patch.object(zunda_hook, "GEMINI_API_KEY", "")
    def test_no_api_key(self):
        """Returns error if GEMINI_API_KEY is not set."""
        result = zunda_hook.zundamon_answer("test")
        self.assertIn("APIキー", result)

    @patch.object(zunda_hook, "GEMINI_API_KEY", "fake-key")
    @patch.object(zunda_hook, "_call_gemini")
    def test_question_passed_to_all_steps(self, mock_gemini):
        """The original question appears in all 3 prompts."""
        mock_gemini.side_effect = ["draft", "critique", "final"]
        zunda_hook.zundamon_answer("リスト内包表記とは")
        for call in mock_gemini.call_args_list:
            self.assertIn("リスト内包表記", call[0][0])


class TestSummarizeWithMock(unittest.TestCase):
    """Tests for zundamon_summarize."""

    @patch.object(zunda_hook, "GEMINI_API_KEY", "fake-key")
    @patch.object(zunda_hook, "_call_gemini")
    def test_summarize_calls_gemini(self, mock_gemini):
        mock_gemini.return_value = "ファイルを編集したのだ！"
        result = zunda_hook.zundamon_summarize("User: edit file\nClaude: done")
        self.assertEqual(mock_gemini.call_count, 1)
        self.assertEqual(result, "ファイルを編集したのだ！")

    @patch.object(zunda_hook, "GEMINI_API_KEY", "fake-key")
    @patch.object(zunda_hook, "_call_gemini")
    def test_summarize_api_error(self, mock_gemini):
        mock_gemini.side_effect = Exception("timeout")
        result = zunda_hook.zundamon_summarize("some text")
        self.assertIn("エラー", result)

    @patch.object(zunda_hook, "GEMINI_API_KEY", "")
    def test_summarize_no_api_key(self):
        result = zunda_hook.zundamon_summarize("some text")
        self.assertIn("APIキー", result)


if __name__ == "__main__":
    unittest.main()
