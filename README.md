# AI Gmail Organizer

AI-powered Windows desktop overlay for intelligent Gmail organization and productivity automation.

## v0.4 — AI inbox organization

v0.4 adds read-only inbox analysis. The app can retrieve a small inbox sample, classify messages into practical categories, and present a summary in the desktop overlay. With `OPENAI_API_KEY` configured, classification is delegated to an AI model; without it, a deterministic local classifier keeps the feature usable without external AI credentials.

### Current capabilities

- Borderless, always-on-top Windows overlay
- Chat-style command interface with quick actions
- Gmail OAuth 2.0 desktop authentication
- Read-only Gmail search and inbox retrieval
- AI or local-rule email classification
- Categories: important, work, personal, promotions, newsletters, other
- Inbox category counts and top-message explanations
- Safe v0.4 design: no Gmail messages are modified
- Automated classifier and agent tests

### Example commands

```text
Organize my inbox
Find unread Gmail emails
Show my starred emails
Find emails from recruiter@example.com
```

### Google Cloud setup

1. Enable the **Gmail API** in Google Cloud.
2. Create an OAuth client for a **Desktop app**.
3. Download the OAuth client JSON as `credentials.json` in the project root.
4. Run the application and issue a Gmail command.
5. Complete Google's browser-based authorization. The app stores the local token in `token.json`.

**Never commit `credentials.json` or `token.json`.** They are ignored by `.gitignore`.

### AI provider (optional)

Put the following in `.env`:

```text
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5.6-luna
```

Without an AI key, v0.4 falls back to local classification rules.

## Roadmap

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

Run tests with:

```powershell
pytest
```

See `docs/architecture.md` for the architecture and roadmap.
