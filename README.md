# AI Gmail Organizer

AI-powered Windows desktop overlay for intelligent Gmail organization and productivity automation.

## v0.2 — AI command surface

The overlay is now interactive: users can enter natural-language commands and receive responses through a small command-agent layer. The app works in local demo mode without credentials and can optionally call an OpenAI Responses API model when `OPENAI_API_KEY` is configured.

### Current capabilities

- Borderless, always-on-top Windows overlay
- Chat-style command interface
- Local demo mode with Gmail-aware responses
- Optional OpenAI Responses API integration
- Environment-based configuration
- Basic automated tests for the command agent

### Roadmap

- **v0.3:** Gmail OAuth and inbox retrieval
- **v0.4:** Email search and AI categorization
- **v0.5:** Gmail labels, archive actions, and confirmation flow
- **v0.6:** Windows automation tools
- **v1.0:** Polished desktop assistant with Gmail + Windows workflows

## Tech stack

Python · PySide6 · OpenAI Responses API · Gmail API (planned) · SQLite (planned) · pytest

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

Without an API key, the application stays in safe demo mode and does not perform Gmail actions.

Run tests with:

```powershell
pytest
```

See `docs/architecture.md` for the current architecture and roadmap.
