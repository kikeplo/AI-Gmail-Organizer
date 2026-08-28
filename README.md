# AI Gmail Organizer

AI-powered Windows desktop assistant for intelligent Gmail organization and productivity automation.

## v0.6 — Windows automation

v0.6 adds a Windows automation layer to the existing Gmail assistant. The application can inspect the active desktop window and perform a small set of explicit window-management actions through structured tools.

### Current capabilities

- Borderless, always-on-top Windows overlay
- Chat-style command interface with quick actions
- Gmail OAuth 2.0 desktop authentication
- Gmail search and inbox retrieval
- AI or local-rule email classification
- Archive Gmail messages
- Create/find and apply Gmail labels
- Explicit confirmation dialog before every Gmail mutation
- Windows active-window inspection
- Windows minimize, maximize, and restore actions
- Safe executable launching helper without shell command strings
- Platform guard so Windows-only tools fail clearly elsewhere
- Automated tests

### Example commands

```text
What window is active?
Minimize the active window
Maximize the active window
Restore the active window
Find my unread Gmail emails
Archive my unread Gmail emails
```

Gmail mutations still require explicit confirmation. Windows window-management commands in v0.6 are limited to the supported operations above.

### Google Cloud setup

1. Enable the **Gmail API** in Google Cloud.
2. Create an OAuth client for a **Desktop app**.
3. Download the OAuth client JSON as `credentials.json` in the project root.
4. Run the application and issue a Gmail command.
5. Complete Google's browser-based authorization. The app stores the local token in `token.json`.

For the Gmail mutation features, the OAuth scope includes `gmail.modify`.

**Never commit `credentials.json` or `token.json`.** They are ignored by `.gitignore`.

### AI provider (optional)

Put the following in `.env`:

```text
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5.6-luna
```

Without an AI key, supported Gmail and Windows intents still use deterministic routing.

## Roadmap

- **v0.7:** Persistent local memory and analytics
- **v1.0:** Polished desktop assistant with Gmail + Windows workflows

## Tech stack

Python · PySide6 · OpenAI Responses API · Gmail API · Google OAuth 2.0 · pywin32 · pytest

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
copy .env.example .env
python main.py
```

Run tests with:

```powershell
pytest
```

See `docs/architecture.md` for the architecture and safety boundaries.
