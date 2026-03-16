#!/usr/bin/env python3
"""
Claude Code Hook -> Zundamon progress reporter & Q&A.

PostToolUse: Reports file edit progress via VOICEVOX speech.
UserPromptSubmit: Answers @zunda questions via Gemini + VOICEVOX.
"""

import json
import sys
import os
import subprocess
import tempfile
import urllib.request
import urllib.parse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_env():
    """Load key-value pairs from SCRIPT_DIR/.env into os.environ."""
    env_path = os.path.join(SCRIPT_DIR, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Existing env vars take precedence
            if key and key not in os.environ:
                os.environ[key] = value


load_env()

# === Configuration ===
VOICEVOX_HOST = os.environ.get("VOICEVOX_HOST", "http://localhost:50021")
VOICEVOX_SPEAKER = int(os.environ.get("VOICEVOX_SPEAKER", "3"))  # 3 = Zundamon (Normal)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
LOG_FILE = os.path.join(SCRIPT_DIR, "zunda_hook.log")
ZUNDAMON_PREFIX = "@zunda "


def zundamon_summarize(conversation: str) -> str:
    """Summarize a conversation in Zundamon's speaking style via Gemini API."""
    if not GEMINI_API_KEY:
        return "Gemini APIキーが設定されてないのだ！GEMINI_API_KEY環境変数を設定するのだ！"

    prompt = (
        "あなたは「ずんだもん」です。東北地方の妖精で、語尾に「なのだ」「のだ」をつけて話します。\n"
        "以下のAIアシスタント(Claude)と開発者の会話を読んで、**開発の進捗を30文字〜80文字程度で短く報告**してください。\n"
        "ルール:\n"
        "- 語尾は「なのだ」「のだ」「だよ」を使う\n"
        "- 技術用語はそのまま使ってOK\n"
        "- 明るく元気な口調で\n"
        "- 余計な説明や前置きは不要。報告文だけ出力すること\n\n"
        f"会話内容:\n{conversation}"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 150, "temperature": 0.8},
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return text.strip()
    except Exception as e:
        return f"Gemini APIでエラーが出たのだ…{e}"


def zundamon_answer(question: str) -> str:
    """Answer a user question as Zundamon via Gemini API."""
    if not GEMINI_API_KEY:
        return "Gemini APIキーが設定されてないのだ！"

    prompt = (
        "あなたは「ずんだもん」です。東北地方の妖精で、語尾に「なのだ」「のだ」をつけて話します。\n"
        "以下のユーザーの質問に、ずんだもんとして**正確かつ親切に**答えてください。\n"
        "ルール:\n"
        "- 語尾は「なのだ」「のだ」「だよ」を使う\n"
        "- 技術用語はそのまま使ってOK\n"
        "- 明るく元気な口調で\n"
        "- 200文字以内で簡潔に答えること\n"
        "- 余計な前置きは不要。回答だけ出力すること\n\n"
        f"質問: {question}"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 300, "temperature": 0.7},
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return text.strip()
    except Exception as e:
        return f"うまく答えられなかったのだ…{e}"


def speak_voicevox(text: str) -> None:
    """Synthesize and play speech via VOICEVOX."""
    # 1. Generate audio query
    query_url = f"{VOICEVOX_HOST}/audio_query?text={urllib.parse.quote(text)}&speaker={VOICEVOX_SPEAKER}"
    req = urllib.request.Request(query_url, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            query_json = resp.read()
    except Exception as e:
        print(f"[zunda_hook] VOICEVOX audio_query failed: {e}", file=sys.stderr)
        return

    # 2. Synthesize audio
    synth_url = f"{VOICEVOX_HOST}/synthesis?speaker={VOICEVOX_SPEAKER}"
    req = urllib.request.Request(
        synth_url,
        data=query_json,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            wav_data = resp.read()
    except Exception as e:
        print(f"[zunda_hook] VOICEVOX synthesis failed: {e}", file=sys.stderr)
        return

    # 3. Play audio (fallback chain: aplay -> paplay -> ffplay)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(wav_data)
        tmp_path = tmp.name

    try:
        for player in ["aplay", "paplay", "ffplay -nodisp -autoexit"]:
            cmd = f"{player} {tmp_path}"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=30)
            if result.returncode == 0:
                break
    except Exception as e:
        print(f"[zunda_hook] audio playback failed: {e}", file=sys.stderr)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def log(msg: str) -> None:
    """Write a debug log entry to the log file."""
    import datetime
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        ts = datetime.datetime.now().isoformat()
        f.write(f"[{ts}] {msg}\n")


def main():
    """Read hook input from stdin and dispatch to the appropriate handler."""
    try:
        raw = sys.stdin.read()
        log(f"stdin: {raw[:500]}")
        hook_input = json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        log(f"stdin parse error: {e}")
        return

    event_name = hook_input.get("hook_event_name", "")

    if event_name == "UserPromptSubmit":
        handle_user_prompt(hook_input)
    elif event_name == "PostToolUse":
        handle_post_tool_use(hook_input)
    else:
        log(f"Unknown event: {event_name}, skipping")


def handle_user_prompt(hook_input: dict):
    """Handle UserPromptSubmit: answer @zunda questions."""
    user_prompt = hook_input.get("prompt", "")
    if not user_prompt:
        log("No prompt field, skipping")
        return

    # Check for @zunda prefix; return immediately if not matched
    if not user_prompt.startswith(ZUNDAMON_PREFIX):
        return

    question = user_prompt[len(ZUNDAMON_PREFIX):].strip()
    if not question:
        log("Empty question after @zunda, skipping")
        print("Enter a question! e.g. @zunda What is Python?", file=sys.stderr)
        sys.exit(2)

    log(f"zundamon question: {question[:200]}")

    # Run Gemini + VOICEVOX in background, return immediately
    subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "--answer", question],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Block the prompt from being sent to Claude via exit code 2
    print("Zundamon is thinking...", file=sys.stderr)
    sys.exit(2)


def run_answer_mode(question: str):
    """Background mode: answer a question and play speech."""
    answer = zundamon_answer(question)
    log(f"zundamon answer: {answer}")
    speak_voicevox(answer)
    log("done (user prompt Q&A)")


def handle_post_tool_use(hook_input: dict):
    """Handle PostToolUse: report file edit progress."""
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if not tool_name:
        log("No tool_name, skipping")
        return

    # Build summary text from edit details
    file_path = tool_input.get("file_path", "unknown file")
    if tool_name == "Edit":
        old_str = tool_input.get("old_string", "")[:100]
        new_str = tool_input.get("new_string", "")[:100]
        conversation = f"Edited {file_path}: '{old_str}' -> '{new_str}'"
    elif tool_name == "Write":
        content_preview = tool_input.get("content", "")[:150]
        conversation = f"Created {file_path}: {content_preview}"
    else:
        log(f"Unexpected tool: {tool_name}, skipping")
        return

    log(f"conversation: {conversation[:200]}")

    # Convert to Zundamon style
    zunda_text = zundamon_summarize(conversation)
    log(f"zunda_text: {zunda_text}")

    # Play via VOICEVOX
    speak_voicevox(zunda_text)
    log("done")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--answer":
        run_answer_mode(sys.argv[2])
    else:
        main()
