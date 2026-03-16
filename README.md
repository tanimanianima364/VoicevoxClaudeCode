# VoicevoxClaudeCode

A tool that makes Zundamon voice-report development progress whenever Claude Code edits files.

## How It Works

Uses Claude Code's **PostToolUse hook** to asynchronously run the following pipeline on each file edit (Edit/Write):

```
Claude Code edits a file (PostToolUse hook fires)
  ↓
zunda_hook.py receives edit details and adds to queue
  ↓
Batch processing: fires after 3s of inactivity or 5 queued edits
  ↓
Gemini API summarizes edits in Zundamon's speaking style
  ↓
VOICEVOX synthesizes speech → plays audio
```

## Session Control

Disabled by default. Explicitly enable it per Claude Code session.

| Command | Action |
|---|---|
| `@zunda on` | Enable Zundamon for this session |
| `@zunda off` | Disable Zundamon for this session |

Managed per session ID, so it does not affect other Claude Code sessions running in different projects.

## Ask Zundamon a Question

Type `@zunda` followed by a question, and Zundamon will answer via voice.

```
@zunda What is a Python list comprehension?
```

Prompts starting with `@zunda` are **not sent to Claude** (exit code 2). The Gemini + VOICEVOX pipeline runs in the background.

## Batch Processing

Consecutive edits are batched into a single voice report.

- **Time-based**: Reports after 3 seconds of no new edits
- **Count-based**: Reports immediately when 5 edits accumulate

When multiple sessions are active simultaneously, audio playback is serialized via a lock file — no overlapping speech.

## Key Features

- Registered with `async: true`, so it **does not slow down** Claude Code
- Globally registered in `~/.claude/settings.json`, works in **any directory**
- **Opt-in per session** via `@zunda on` (default: OFF)

## Requirements

- Python 3
- [VOICEVOX](https://voicevox.hiroshiba.jp/) (running locally, default `http://localhost:50021`)
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

### 2. Start VOICEVOX

Start the VOICEVOX engine so it is accessible at `http://localhost:50021`.

With Docker:

```bash
docker run -d --name voicevox -p 50021:50021 voicevox/voicevox_engine:cpu-ubuntu20.04-latest
```

### 3. Configure Hooks

Ensure `~/.claude/settings.json` contains the following:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
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
