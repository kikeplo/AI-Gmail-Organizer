# AI Gmail Organizer

AI-powered Windows desktop assistant for intelligent Gmail organization and productivity automation.

## v0.5 — confirmed Gmail actions

v0.5 moves beyond read-only inbox analysis. The application can now plan Gmail mutations such as archiving messages and applying labels, then requires explicit user confirmation before executing them.

### Current capabilities

- Borderless, always-on-top Windows overlay
- Chat-style command interface with quick actions
- Gmail OAuth 2.0 desktop authentication
- Gmail search and inbox retrieval
- AI or local-rule email classification
- Categories: important, work, personal, promotions, newsletters, other
- Archive Gmail messages
- Create/find and apply Gmail labels
- Explicit confirmation dialog before every Gmail mutation
- Cancellation path that leaves Gmail unchanged
- Local credential/token protection through `.gitignore`
- Automated tests

### Example commands

```text
Organize my inbox
Find my unread Gmail emails
Archive my unread Gmail emails
Label my unread Gmail emails Work
```

For mutating commands, the app first shows what will happen. Gmail is only changed after the user selects **Yes** in the confirmation dialog.

### Google Cloud setup

1. Enable the **Gmail API** in Google Cloud.
2. Create an OAuth client for a **Desktop app**.
3. Download the OAuth client JSON as `credentials.json` in the project root.
4. Run the application and issue a Gmail command.
5. Complete Google's browser-based authorization. The app stores the local token in `token.json`.

For v0.5 the OAuth scope includes `gmail.modify`, which is required for label and archive operations.

**Never commit `credentials.json` or `token.json`.** They are ignored by `.gitignore`.

### AI provider (optional)

Put the following in `.env`:

```text
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5.6-luna
```

Without an AI key, the deterministic command path remains available for supported Gmail operations.

## Roadmap

- **v0.6:** Windows automation tools
- **v0.7:** Persistent local memory and analytics
- **v1.0:** Polished desktop assistant with Gmail + Windows workflows

## Tech stack

Python · PySide6 · OpenAI Responses API · Gmail API · Google OAuth 2.0 · pytest

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
