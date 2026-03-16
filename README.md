# VoicevoxClaudeCode

A tool that makes Zundamon (a character from VOICEVOX) report development progress via voice whenever Claude Code edits files.

## How It Works

Uses Claude Code's **PostToolUse hook** to run the following pipeline asynchronously on file edits (Edit/Write):

```
Claude Code edits a file (PostToolUse hook fires)
  ↓
zunda_hook.py receives edit details via stdin
  ↓
Gemini API summarizes in Zundamon's speaking style
  ↓
VOICEVOX synthesizes speech → plays audio
```

## Ask Zundamon Directly

Type `@zunda` followed by a question in the Claude Code prompt, and Zundamon will answer with voice.

```
@zunda What is a Python list comprehension?
```

Zundamon generates an answer via Gemini API and reads it aloud with VOICEVOX.

**Note**: This feature uses the `UserPromptSubmit` hook. Prompts starting with `@zunda` are blocked from being sent to Claude (the hook exits with code 2). The Gemini + VOICEVOX pipeline runs in the background so Claude Code is not blocked.

- The PostToolUse hook is registered with `async: true`, so it does not affect Claude Code's response speed
- Hooks are registered globally in `~/.claude/settings.json`, so they work in any directory

## About Paths in Examples

The hook configuration examples below use `/home/tanima/VoicevoxClaudeCode/` as the script path. Replace this with your own path.

## Prerequisites

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
            "command": "python3 /home/tanima/VoicevoxClaudeCode/zunda_hook.py",
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
            "command": "python3 /home/tanima/VoicevoxClaudeCode/zunda_hook.py",
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

# Test Zundamon Q&A (Gemini API only)
python3 test_hook.py --qa

# Test Zundamon Q&A (Gemini + VOICEVOX playback)
python3 test_hook.py --qa --speak

# Simulate UserPromptSubmit hook
python3 test_hook.py --qa-hook

# Full pipeline test with real transcript
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
├── .env             # API keys and settings (gitignored)
├── .env.example     # Template for .env
├── LICENSE
└── README.md
```

## Credits & License

- VOICEVOX:ずんだもん
- Character: Zundamon (Tohoku Zunko & Zundamon Project / SSS LLC.)
- Character guideline compliance mark: （ず・ω・きょ）
- Voice library terms: https://zunko.jp/con_ongen_kiyaku.html

Source code in this repository is released under the MIT License.
