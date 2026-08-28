# AI Gmail Organizer

AI-powered Windows desktop assistant for intelligent Gmail organization and productivity automation.

## v0.7 — local memory & analytics

v0.7 adds a privacy-friendly local memory layer. The assistant stores command history and response metadata in a local SQLite database so sessions can retain lightweight context without requiring a hosted database.

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
- Persistent local interaction history in SQLite
- Local usage analytics by response mode
- History and analytics commands in the overlay
- Automated tests

### Memory commands

```text
Show my history
What did I ask recently?
Show usage analytics
Show my stats
```

Memory is stored locally in `data/assistant.db` and is excluded from version control. No hosted memory service is required.

### Gmail commands

```text
Find my unread Gmail emails
Organize my inbox
Archive my unread Gmail emails
Label my unread Gmail emails Work
```

Gmail mutations require explicit confirmation before the message state is changed.

### Windows commands

```text
What window is active?
Minimize the active window
Maximize the active window
Restore the active window
```

### Google Cloud setup

1. Enable the **Gmail API** in Google Cloud.
2. Create an OAuth client for a **Desktop app**.
3. Download the OAuth client JSON as `credentials.json` in the project root.
4. Run the application and issue a Gmail command.
5. Complete Google's browser-based authorization. The app stores the local token in `token.json`.

For Gmail mutation features, the OAuth scope includes `gmail.modify`.

**Never commit `credentials.json` or `token.json`.** They are ignored by `.gitignore`.

### AI provider (optional)

Put the following in `.env`:

```text
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5.6-luna
```

Without an AI key, supported Gmail and Windows intents still use deterministic routing.

## Tech stack

Python · PySide6 · OpenAI Responses API · Gmail API · Google OAuth 2.0 · SQLite · pywin32 · pytest

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

## Roadmap

- **v1.0:** Polished desktop assistant with Gmail + Windows workflows
