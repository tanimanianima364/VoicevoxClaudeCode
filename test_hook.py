#!/usr/bin/env python3
"""
Tests for zunda_hook.py.
Allows testing individual components without requiring a live Claude Code session.
"""

import json
import sys
import os

# Add project path
sys.path.insert(0, os.path.dirname(__file__))
from zunda_hook import zundamon_summarize, zundamon_answer, speak_voicevox


def test_gemini():
    """Test Gemini API summarization in Zundamon style."""
    test_conversation = (
        "User: I want to use hooks to make Zundamon speak via VOICEVOX\n"
        "Claude: I implemented it using a Stop hook that runs a script when Claude finishes responding."
    )
    print("=== Gemini API Summarize Test ===")
    result = zundamon_summarize(test_conversation)
    print(f"Zundamon: {result}")
    return result


def test_voicevox(text: str):
    """Test VOICEVOX speech playback."""
    print("\n=== VOICEVOX Playback Test ===")
    print(f"Text: {text}")
    speak_voicevox(text)
    print("Playback complete!")


def test_hook_stdin():
    """Test with the same stdin format as an actual hook invocation."""
    print("\n=== Hook stdin Simulation ===")
    # Find an existing transcript
    claude_dir = os.path.expanduser("~/.claude/projects")
    transcript = None
    for root, dirs, files in os.walk(claude_dir):
        for f in files:
            if f.endswith(".jsonl") and "subagent" not in root:
                transcript = os.path.join(root, f)
                break
        if transcript:
            break

    if transcript:
        print(f"Transcript: {transcript}")
        hook_input = json.dumps({"transcript_path": transcript})
        import subprocess
        result = subprocess.run(
            ["python3", os.path.join(os.path.dirname(__file__), "zunda_hook.py")],
            input=hook_input,
            capture_output=True,
            text=True,
            timeout=30,
        )
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
    else:
        print("No transcript found")


def test_gemini_qa():
    """Test Gemini API Q&A in Zundamon style."""
    print("=== Gemini Q&A Test ===")
    result = zundamon_answer("Pythonのデコレータって何？")
    print(f"Zundamon: {result}")
    return result


def test_user_prompt_qa():
    """Simulate a UserPromptSubmit hook for Zundamon Q&A."""
    print("\n=== UserPromptSubmit Q&A Test ===")
    hook_input = json.dumps({
        "session_id": "test-session",
        "transcript_path": "",
        "cwd": os.getcwd(),
        "permission_mode": "default",
        "hook_event_name": "UserPromptSubmit",
        "prompt": "@zunda What is a Python list comprehension?"
    })
    import subprocess
    result = subprocess.run(
        ["python3", os.path.join(os.path.dirname(__file__), "zunda_hook.py")],
        input=hook_input,
        capture_output=True,
        text=True,
        timeout=30,
    )
    print(f"stdout: {result.stdout}")
    print(f"stderr: {result.stderr}")
    print(f"return code: {result.returncode}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        test_hook_stdin()
    elif len(sys.argv) > 1 and sys.argv[1] == "--qa":
        text = test_gemini_qa()
        if text and "--speak" in sys.argv:
            test_voicevox(text)
    elif len(sys.argv) > 1 and sys.argv[1] == "--qa-hook":
        test_user_prompt_qa()
    else:
        text = test_gemini()
        if text and "--speak" in sys.argv:
            test_voicevox(text)
