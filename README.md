# AI Gmail Organizer

Windows desktop assistant for Gmail organization, window controls, and local productivity workflows.

## Features

**Gmail**
- OAuth 2.0 authentication
- Search unread, starred, recent, and sender-specific messages
- Inbox classification and summaries
- Create and apply Gmail labels
- Archive messages
- Confirmation before actions that change Gmail

**Windows**
- Inspect the active window
- Minimize, maximize, and restore the active window
- Small explicit automation surface rather than arbitrary shell commands

**Local assistant**
- Natural-language command interface
- Optional OpenAI Responses API integration
- Local interaction history in SQLite
- Usage statistics
- Deterministic fallbacks when external AI services are not configured

### Example commands

```text
Organize my inbox
Find unread Gmail emails
Archive my unread Gmail emails
Label my unread Gmail emails Work
What window is active?
Minimize the active window
Show my history
Show usage analytics
```

## Architecture

```text
                    Windows Overlay (PySide6)
                              │
                              ▼
                         CommandAgent
                  ┌───────────┼───────────┐
                  ▼           ▼           ▼
             Gmail tools  Windows tools  Local memory
                  │           │           │
                  ▼           ▼           ▼
             Gmail API     pywin32      SQLite
                  │
             OAuth 2.0
                              
                       Optional AI provider
                              │
                              ▼
                     OpenAI Responses API
```

The UI is responsible for presentation and confirmation. The command layer routes requests to the Gmail, Windows, and local-memory services. Gmail mutations are confirmation-protected, and arbitrary shell commands are not exposed through the natural-language interface.

## Setup

### 1. Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
copy .env.example .env
```

### 2. Configure Gmail

1. Enable the Gmail API in Google Cloud.
2. Create an OAuth client for a Desktop app.
3. Save the downloaded client JSON as `credentials.json` in the project root.
4. Run the application and issue a Gmail command.
5. Complete Google's browser authorization flow.

The application stores the local OAuth token in `token.json`.

### 3. Configure the AI provider (optional)

Set these values in `.env`:

```text
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=your_model_name
```

The model is intentionally configured by the user rather than hard-coded. Without an API key/model, the application uses the local command paths.

### 4. Run

```powershell
python main.py
```

### 5. Test

```powershell
pytest
```

## Security

Keep `credentials.json`, `token.json`, `.env`, and local SQLite databases out of version control. They are excluded by `.gitignore`.

The Gmail client uses OAuth scopes matching the supported features. Every Gmail action that changes message state goes through the confirmation step in the UI.

## Development history

- **v0.1** — desktop overlay foundation
- **v0.2** — interactive command interface
- **v0.3** — Gmail OAuth and read-only retrieval
- **v0.4** — inbox classification and summaries
- **v0.5** — confirmed Gmail labels and archive actions
- **v0.6** — Windows automation tools
- **v0.7** — local memory and usage analytics
- **v1.0.0** — unified desktop assistant
