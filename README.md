# VoicevoxClaudeCode

Zundamon voice-reports development progress when Claude Code finishes a response.

## How It Works

Uses Claude Code's **Stop hook** to summarize what Claude did at the end of each turn.

```
Claude Code finishes responding (Stop hook fires)
  ↓
zunda_hook.py receives last_assistant_message
  ↓
Gemini API summarizes it in Zundamon's speaking style
  ↓
VOICEVOX synthesizes speech → plays audio
```

## Project Control

Disabled by default. Enable per project directory with `@zunda on` in any Claude Code session.

| Command | Action |
|---|---|
| `@zunda on` | Enable Zundamon for this project (auto-starts VOICEVOX Docker container) |
| `@zunda off` | Disable Zundamon for this project |
| `/exit` | Automatically disables Zundamon for this project |

Managed per project directory (cwd), so enabling in one project does not affect others. Persists across session changes within the same directory.

## Ask Zundamon a Question

Type `@zunda` followed by a question, and Zundamon will answer via voice.

```
@zunda What is a Python list comprehension?
```

Prompts starting with `@zunda` are **not sent to Claude** (exit code 2). The Gemini + VOICEVOX pipeline runs in the background.

## Concurrent Playback

When multiple projects trigger speech simultaneously, a lock file serializes audio playback — no overlapping speech. Gemini API calls run in parallel; only playback is queued.

## Key Features

- **Stop hook** with `async: true` — does not slow down Claude Code
- Globally registered in `~/.claude/settings.json` — works in any directory
- **Opt-in per project** via `@zunda on` (default: OFF)
- **Auto-starts VOICEVOX** Docker container on `@zunda on` if not running

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

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | (required) | Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model to use |
| `VOICEVOX_HOST` | `http://localhost:50021` | VOICEVOX engine URL |
| `VOICEVOX_SPEAKER` | `3` | Speaker ID (3 = Zundamon Normal) |

## File Structure

```
VoicevoxClaudeCode/
├── zunda_hook.py    # Main hook script
├── test_hook.py     # Test script
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
