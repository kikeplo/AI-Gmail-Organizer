# AI Gmail Organizer

AI-powered Windows desktop overlay for intelligent Gmail organization and productivity automation.

## v0.3 — Gmail connection

v0.3 adds the first real Gmail integration. The app can authenticate with Google using OAuth 2.0 and retrieve recent messages through the Gmail API. The current Gmail scope is **read-only**; destructive or externally visible Gmail actions are not implemented yet.

### Current capabilities

- Borderless, always-on-top Windows overlay
- Chat-style command interface
- Local demo mode
- Optional OpenAI Responses API integration
- Gmail OAuth 2.0 desktop authentication
- Read-only Gmail message search
- Natural-language shortcuts for unread, starred, and sender-based searches
- Local OAuth token persistence
- Automated tests for Gmail query routing

### Google Cloud setup

1. Create or select a Google Cloud project.
2. Enable the **Gmail API**.
3. Configure an OAuth client for a **Desktop app**.
4. Download the OAuth client JSON and save it as `credentials.json` in the project root.
5. Run the application and issue a Gmail command such as:

```text
Find my unread Gmail emails
```

Google will open a browser for authorization. After successful authorization, the app stores the local access/refresh token in `token.json`.

**Never commit `credentials.json` or `token.json`.** They are explicitly ignored by `.gitignore`.

### Example commands

```text
Find unread Gmail emails
Show my starred emails
Find emails from recruiter@example.com
Show recent emails
```

The Gmail API's `messages.list` operation supports Gmail-style search queries such as `is:unread` and `from:...`. 

### Roadmap

- **v0.4:** AI-powered email classification and inbox summaries
- **v0.5:** Labels, archive actions, and explicit confirmation flow
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

To enable the optional AI provider, put your API key in `.env`:

```text
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5.6-luna
```

Without an API key, the application still supports the Gmail command path once Google OAuth is configured.

Run tests with:

```powershell
pytest
```

See `docs/architecture.md` for the architecture and roadmap.
