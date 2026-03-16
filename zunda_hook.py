#!/usr/bin/env python3
"""
Claude Code Hook -> Zundamon progress reporter & Q&A.

Stop: Summarizes what Claude did and reports via VOICEVOX speech.
UserPromptSubmit: Handles @zunda on/off/questions.
"""

import json
import sys
import os
import fcntl
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
            if key and key not in os.environ:
                os.environ[key] = value


load_env()

# === Configuration ===
VOICEVOX_HOST = os.environ.get("VOICEVOX_HOST", "http://localhost:50021")
VOICEVOX_SPEAKER = max(0, int(os.environ.get("VOICEVOX_SPEAKER", "3")))
VOICEVOX_SPEED = min(2.0, max(0.5, float(os.environ.get("VOICEVOX_SPEED", "1.4"))))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
LOG_FILE = os.path.join(SCRIPT_DIR, "zunda_hook.log")
LOCK_FILE = os.path.join(SCRIPT_DIR, ".voicevox.lock")
ACTIVE_PROJECTS_FILE = os.path.join(SCRIPT_DIR, ".active_projects")
TRANSCRIPT_OFFSETS_FILE = os.path.join(SCRIPT_DIR, ".transcript_offsets")
FULL_FLAG_FILE = os.path.join(SCRIPT_DIR, ".next_full")
MAX_CONVERSATION_CHARS = 3000000  # ~1M tokens for Gemini
ZUNDAMON_PREFIX = "@zunda "


def zundamon_summarize(text: str) -> str:
    """Summarize Claude's work in Zundamon's speaking style via Gemini API."""
    if not GEMINI_API_KEY:
        return "Gemini APIキーが設定されてないのだ！"

    prompt = (
        "あなたは「ずんだもん」です。東北地方の妖精で、語尾に「なのだ」「のだ」をつけて話します。\n"
        "以下はAIアシスタント(Claude)と開発者の会話全体です。\n"
        "この会話を読んで、**Claudeが何をしたか・何が決まったか・何が変わったかを具体的に、100文字〜200文字程度で要約報告**してください。\n"
        "ルール:\n"
        "- 語尾は「なのだ」「のだ」「だよ」を使う\n"
        "- ファイル名や機能名など具体的な内容を含めること\n"
        "- 技術用語はそのまま使ってOK\n"
        "- 明るく元気な口調で\n"
        "- 余計な前置きは不要。報告文だけ出力すること\n\n"
        f"会話:\n{text}"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 300, "temperature": 0.8},
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
    """Synthesize and play speech via VOICEVOX with lock serialization."""
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
    except Exception as e:
        log(f"Lock error: {e}")
        lock_fd.close()
        return

    try:
        _play_voicevox(text)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def _play_voicevox(text: str) -> None:
    """Internal: synthesize and play audio (called with lock held)."""
    query_url = f"{VOICEVOX_HOST}/audio_query?text={urllib.parse.quote(text)}&speaker={VOICEVOX_SPEAKER}"
    req = urllib.request.Request(query_url, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            query_data = json.loads(resp.read())
    except Exception as e:
        print(f"[zunda_hook] VOICEVOX audio_query failed: {e}", file=sys.stderr)
        return

    query_data["speedScale"] = VOICEVOX_SPEED
    query_json = json.dumps(query_data).encode("utf-8")

    synth_url = f"{VOICEVOX_HOST}/synthesis?speaker={VOICEVOX_SPEAKER}"
    req = urllib.request.Request(
        synth_url, data=query_json,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            wav_data = resp.read()
    except Exception as e:
        print(f"[zunda_hook] VOICEVOX synthesis failed: {e}", file=sys.stderr)
        return

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


def ensure_voicevox() -> None:
    """Ensure VOICEVOX engine is running. Start Docker container if needed."""
    # Check if already accessible
    try:
        req = urllib.request.Request(f"{VOICEVOX_HOST}/version")
        with urllib.request.urlopen(req, timeout=2):
            return  # Already running
    except Exception:
        pass

    # Try starting existing container
    log("VOICEVOX not running, attempting docker start...")
    result = subprocess.run(
        ["docker", "start", "voicevox"],
        capture_output=True, timeout=10,
    )
    if result.returncode != 0:
        # Container doesn't exist, create it
        log("Container not found, creating...")
        subprocess.run(
            ["docker", "run", "-d", "--name", "voicevox",
             "-p", "50021:50021",
             "voicevox/voicevox_engine:cpu-ubuntu20.04-latest"],
            capture_output=True, timeout=120,
        )

    # Wait for VOICEVOX to become ready (up to 30s)
    import time
    for _ in range(30):
        try:
            req = urllib.request.Request(f"{VOICEVOX_HOST}/version")
            with urllib.request.urlopen(req, timeout=2):
                log("VOICEVOX is ready")
                return
        except Exception:
            time.sleep(1)
    log("VOICEVOX failed to start within 30s")


def is_project_active(cwd: str) -> bool:
    if not cwd or not os.path.exists(ACTIVE_PROJECTS_FILE):
        return False
    with open(ACTIVE_PROJECTS_FILE, "r") as f:
        return cwd in f.read().splitlines()


def activate_project(cwd: str) -> None:
    projects = set()
    if os.path.exists(ACTIVE_PROJECTS_FILE):
        with open(ACTIVE_PROJECTS_FILE, "r") as f:
            projects = set(line.strip() for line in f if line.strip())
    projects.add(cwd)
    with open(ACTIVE_PROJECTS_FILE, "w") as f:
        f.write("\n".join(projects) + "\n")


def deactivate_project(cwd: str) -> None:
    if not os.path.exists(ACTIVE_PROJECTS_FILE):
        return
    with open(ACTIVE_PROJECTS_FILE, "r") as f:
        projects = set(line.strip() for line in f if line.strip())
    projects.discard(cwd)
    with open(ACTIVE_PROJECTS_FILE, "w") as f:
        f.write("\n".join(projects) + "\n") if projects else None


def main():
    """Read hook input from stdin and dispatch."""
    try:
        raw = sys.stdin.read()
        log(f"stdin: {raw[:500]}")
        hook_input = json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        log(f"stdin parse error: {e}")
        return

    event_name = hook_input.get("hook_event_name", "")
    cwd = hook_input.get("cwd", "")

    # @zunda on/off / /exit — check before project active gate
    if event_name == "UserPromptSubmit":
        prompt = hook_input.get("prompt", "").strip()
        if prompt == "@zunda on":
            ensure_voicevox()
            activate_project(cwd)
            log(f"Project activated: {cwd}")
            subprocess.Popen(
                [sys.executable, os.path.abspath(__file__), "--answer", "ずんだもん、起動したのだ！よろしくなのだ！"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            print("Zundamon ON!", file=sys.stderr)
            sys.exit(2)
        if prompt == "@zunda off":
            deactivate_project(cwd)
            log(f"Project deactivated: {cwd}")
            subprocess.Popen(
                [sys.executable, os.path.abspath(__file__), "--answer", "ずんだもん、おやすみなのだ！またね！"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            print("Zundamon OFF!", file=sys.stderr)
            sys.exit(2)
        if prompt == "@zunda status":
            active = is_project_active(cwd)
            # Check VOICEVOX
            voicevox_ok = False
            try:
                req = urllib.request.Request(f"{VOICEVOX_HOST}/version")
                with urllib.request.urlopen(req, timeout=2):
                    voicevox_ok = True
            except Exception:
                pass
            # List all active projects
            all_projects = []
            if os.path.exists(ACTIVE_PROJECTS_FILE):
                with open(ACTIVE_PROJECTS_FILE, "r") as f:
                    all_projects = [l.strip() for l in f if l.strip()]
            status = (
                f"Zundamon: {'ON' if active else 'OFF'} (this project)\n"
                f"VOICEVOX: {'Running' if voicevox_ok else 'Not running'} ({VOICEVOX_HOST})\n"
                f"Gemini:   {'Configured' if GEMINI_API_KEY else 'No API key'} ({GEMINI_MODEL})\n"
                f"Speaker:  {VOICEVOX_SPEAKER}\n"
                f"Speed:    {VOICEVOX_SPEED}x\n"
                f"Active projects: {', '.join(all_projects) if all_projects else '(none)'}"
            )
            print(status, file=sys.stderr)
            sys.exit(2)
        if prompt == "@zunda full":
            # Set flag so the next Stop hook sends the full transcript
            with open(FULL_FLAG_FILE, "w") as f:
                f.write(cwd)
            print("Next report will include the full conversation.", file=sys.stderr)
            sys.exit(2)
        if prompt == "/exit" and is_project_active(cwd):
            deactivate_project(cwd)
            log(f"Project auto-deactivated on /exit: {cwd}")
            return

    # Skip if project not active
    if not is_project_active(cwd):
        return

    if event_name == "UserPromptSubmit":
        handle_user_prompt(hook_input)
    elif event_name == "Stop":
        # Check if @zunda full was requested
        full = False
        if os.path.exists(FULL_FLAG_FILE):
            try:
                with open(FULL_FLAG_FILE, "r") as f:
                    if f.read().strip() == cwd:
                        full = True
                os.unlink(FULL_FLAG_FILE)
            except OSError:
                pass
        handle_stop(hook_input, full=full)
    else:
        log(f"Unhandled event: {event_name}")


def handle_user_prompt(hook_input: dict):
    """Handle UserPromptSubmit: answer @zunda questions."""
    user_prompt = hook_input.get("prompt", "")
    if not user_prompt or not user_prompt.startswith(ZUNDAMON_PREFIX):
        return

    question = user_prompt[len(ZUNDAMON_PREFIX):].strip()
    if not question:
        print("Enter a question! e.g. @zunda What is Python?", file=sys.stderr)
        sys.exit(2)

    log(f"zundamon question: {question[:200]}")
    subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "--answer", question],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    print("Zundamon is thinking...", file=sys.stderr)
    sys.exit(2)


def _load_offsets() -> dict:
    """Load transcript byte offsets from file."""
    if not os.path.exists(TRANSCRIPT_OFFSETS_FILE):
        return {}
    with open(TRANSCRIPT_OFFSETS_FILE, "r") as f:
        try:
            return json.loads(f.read())
        except json.JSONDecodeError:
            return {}


def _save_offsets(offsets: dict) -> None:
    """Save transcript byte offsets to file."""
    with open(TRANSCRIPT_OFFSETS_FILE, "w") as f:
        f.write(json.dumps(offsets))


def _parse_transcript_lines(lines: list[str]) -> str:
    """Parse JSONL lines into readable conversation text."""
    messages = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        msg_type = obj.get("type")
        if msg_type not in ("user", "assistant"):
            continue

        content_blocks = obj.get("message", {}).get("content", [])
        texts = []
        for block in content_blocks:
            if block.get("type") == "text":
                text = block["text"]
                if text.startswith("[Request interrupted") or text.startswith("The user doesn't want"):
                    continue
                texts.append(text)

        if texts:
            role = "User" if msg_type == "user" else "Claude"
            messages.append(f"{role}: {' '.join(texts)}")

    return "\n".join(messages)


def read_transcript(transcript_path: str, full: bool = False) -> str:
    """Read the JSONL transcript and extract user/assistant text messages.

    Args:
        transcript_path: Path to the JSONL transcript file.
        full: If True, read the entire transcript. If False, read only new
              lines since the last read (delta mode).
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return ""

    offsets = _load_offsets()
    last_offset = offsets.get(transcript_path, 0) if not full else 0

    with open(transcript_path, "r", encoding="utf-8") as f:
        if last_offset > 0:
            f.seek(last_offset)
        lines = f.readlines()
        new_offset = f.tell()

    # Save new offset
    offsets[transcript_path] = new_offset
    _save_offsets(offsets)

    result = _parse_transcript_lines(lines)
    if len(result) > MAX_CONVERSATION_CHARS:
        result = result[-MAX_CONVERSATION_CHARS:]
    return result


def handle_stop(hook_input: dict, full: bool = False):
    """Handle Stop: summarize the conversation and speak it."""
    if hook_input.get("stop_hook_active"):
        log("stop_hook_active=true, skipping")
        return

    transcript_path = hook_input.get("transcript_path", "")
    conversation = read_transcript(transcript_path, full=full)
    if not conversation:
        conversation = hook_input.get("last_assistant_message", "")
    if not conversation:
        log("No conversation found, skipping")
        return

    mode = "full" if full else "delta"
    log(f"Stop ({mode}): conversation length={len(conversation)}")

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    tmp.write(conversation)
    tmp.close()

    subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "--summarize-file", tmp.name],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def run_summarize_mode(text_file: str):
    """Background mode: read conversation from file, summarize, and speak."""
    try:
        with open(text_file, "r", encoding="utf-8") as f:
            text = f.read()
    finally:
        try:
            os.unlink(text_file)
        except OSError:
            pass

    zunda_text = zundamon_summarize(text)
    log(f"zunda_text: {zunda_text}")
    speak_voicevox(zunda_text)
    log("done (stop summary)")


def run_answer_mode(question: str):
    """Background mode: answer a question and play speech."""
    answer = zundamon_answer(question)
    log(f"zundamon answer: {answer}")
    speak_voicevox(answer)
    log("done (user prompt Q&A)")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--answer":
        run_answer_mode(sys.argv[2])
    elif len(sys.argv) >= 3 and sys.argv[1] == "--summarize-file":
        run_summarize_mode(sys.argv[2])
    else:
        main()
