# VoicevoxClaudeCode

Zundamon voice-reports development progress when Claude Code finishes a response.

## How It Works

Uses Claude Code's **Stop hook** to read the full conversation transcript and summarize what Claude did.

```
Claude Code finishes responding (Stop hook fires)
  ↓
zunda_hook.py reads the conversation transcript (delta since last report)
  ↓
Gemini API (1M token context) summarizes it in Zundamon's speaking style
  ↓
VOICEVOX synthesizes speech → plays audio
```

By default, only **new messages since the last report** are sent to Gemini (delta mode). Use `@zunda full` to include the entire conversation in the next report.

## Commands

| Command | Action |
|---|---|
| `@zunda on` | Enable Zundamon for this project (auto-starts VOICEVOX Docker container) |
| `@zunda off` | Disable Zundamon for this project |
| `@zunda full` | Next report includes the full conversation (one-shot) |
| `@zunda status` | Show current status (project, VOICEVOX, Gemini, speaker, speed) |
| `@zunda <question>` | Ask Zundamon a question (answered via voice) |
| `/exit` | Automatically disables Zundamon for this project |

Managed per project directory (cwd), so enabling in one project does not affect others. Persists across session changes within the same directory.

## Ask Zundamon a Question

Type `@zunda` followed by a question, and Zundamon will answer via voice.

```
@zunda What is a Python list comprehension?
```

Prompts starting with `@zunda` are **not sent to Claude** (exit code 2). The Gemini + VOICEVOX pipeline runs in the background.

### 2-Step Review Pipeline (Fact-Checking)

Questions go through a 2-step pipeline to ensure accuracy:

1. **Draft** — Gemini generates an initial answer (temperature 0.7)
2. **Review & Finalize** — A second Gemini call fact-checks the draft, fixes any inaccuracies, and produces the final Zundamon-style answer (temperature 0.4)

If the draft step fails, an error is returned immediately. If the review step fails, an error is returned.

### Auto Context Detection

Questions are automatically analyzed for conversational references. If hint words are detected (e.g., "さっき", "この", "その", "why did", "the error"), the conversation transcript is included as context for the answer. General knowledge questions are answered without context to save tokens and latency.

## Concurrent Playback

When multiple projects trigger speech simultaneously, a lock file serializes audio playback — no overlapping speech. Gemini API calls run in parallel; only playback is queued.

## Key Features

- **Stop hook** with `async: true` — does not slow down Claude Code
- Globally registered in `~/.claude/settings.json` — works in any directory
- **Opt-in per project** via `@zunda on` (default: OFF)
- **Auto-starts VOICEVOX** Docker container on `@zunda on` if not running
- **Delta mode** by default — only new messages since last report are sent to Gemini
- **Full mode** on demand via `@zunda full` — sends entire conversation (up to 1M tokens)
- **Status check** via `@zunda status`
- **Configurable speech speed** (0.5x–2.0x) with validation
- **2-step review pipeline** for Q&A — Draft → Review & Finalize
- **Auto context detection** — conversation history included only when question references it

## Requirements

- Python 3
- Docker (for VOICEVOX engine)
- [Gemini API key](https://aistudio.google.com/apikey)
- An audio player (`aplay`, `paplay`, or `ffplay`)

## Setup

### 1. Create `.env` file

```bash
cp .env.example .env
```

Edit `.env` and set your Gemini API key:

```
GEMINI_API_KEY=your-api-key-here
```

### 2. Configure Hooks

Add the following to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/VoicevoxClaudeCode/zunda_hook.py",
            "async": true,
            "timeout": 30
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/VoicevoxClaudeCode/zunda_hook.py",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### 3. Enable in a project

In any Claude Code session, type:

```
@zunda on
```

This will automatically start the VOICEVOX Docker container if needed.

## Testing

### Unit tests (no external APIs required)

```bash
python3 test_logic.py -v
```

Covers transcript parsing, delta offset tracking, project activation, command dispatch, speed validation, debate pipeline, and summarization (47 tests).

### Integration tests (requires Gemini API key and/or VOICEVOX)

```bash
# Test Gemini API summarization
python3 test_hook.py

# Test Gemini + VOICEVOX playback
python3 test_hook.py --speak

# Test Zundamon Q&A (Gemini only)
python3 test_hook.py --qa

# Test Zundamon Q&A (Gemini + VOICEVOX playback)
python3 test_hook.py --qa --speak

# Simulate UserPromptSubmit hook
python3 test_hook.py --qa-hook

# Full pipeline test with a real transcript
python3 test_hook.py --full
```

## Configuration

Customize via `.env` or environment variables:

| Variable | Default | Range | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | (required) | | Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | | Gemini model to use |
| `VOICEVOX_HOST` | `http://localhost:50021` | | VOICEVOX engine URL |
| `VOICEVOX_SPEAKER` | `3` | >= 0 | Speaker ID (3 = Zundamon Normal) |
| `VOICEVOX_SPEED` | `1.4` | 0.5–2.0 | Speech speed multiplier |

## File Structure

```
VoicevoxClaudeCode/
├── zunda_hook.py    # Main hook script
├── test_logic.py    # Unit tests (41 tests, no API needed)
├── test_hook.py     # Integration tests (requires APIs)
├── .env             # API keys and settings (git-ignored)
├── .env.example     # Template for .env
├── LICENSE
└── README.md
```

## Credits & License

- VOICEVOX: Zundamon
- Character: Zundamon (Tohoku Zunko & Zundamon Project / SSS LLC.)
- Character guideline compliance mark: (zu/omega/kyo)
- Voice library terms of use: https://zunko.jp/con_ongen_kiyaku.html

Source code is released under the MIT License.
