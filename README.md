# AI Gmail Organizer

AI-powered Windows desktop assistant for Gmail organization, desktop window control, and local productivity workflows.

## v1.0.0 — unified desktop assistant

The project has reached its first complete milestone: Gmail integration, confirmation-protected inbox actions, Windows window automation, local SQLite memory, usage analytics, and a polished always-on-top command center are combined behind one interface.

### What it can do

**Gmail**
- OAuth 2.0 authentication
- Search unread, starred, recent, and sender-specific messages
- Analyze and classify inbox messages
- Apply or create Gmail labels
- Archive messages
- Require explicit confirmation before Gmail mutations

**Windows**
- Inspect the active window
- Minimize, maximize, and restore the active window
- Keep automation behind a small explicit tool surface rather than arbitrary shell commands

**Local assistant features**
- Natural-language command interface
- Optional OpenAI Responses API integration
- Persistent local interaction history
- Lightweight usage analytics
- Local demo/deterministic fallbacks when external AI credentials are unavailable

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

### Architecture

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

The UI handles presentation and confirmation. The agent routes commands to typed service boundaries. Gmail write operations are confirmation-protected, and arbitrary shell command execution is not exposed through natural-language routing.

### Setup

#### 1. Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
copy .env.example .env
```

#### 2. Configure Google OAuth

1. Enable the Gmail API in Google Cloud.
2. Create an OAuth client for a Desktop app.
3. Save the downloaded client JSON as `credentials.json` in the project root.
4. Run the application and issue a Gmail command.
5. Complete Google's browser authorization flow.

The application stores its local OAuth token in `token.json`.

#### 3. Optional AI provider

Add to `.env`:

```text
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5.6-luna
```

#### 4. Run

```powershell
python main.py
```

#### 5. Test

```powershell
pytest
```

### Security notes

Do not commit `credentials.json`, `token.json`, `.env`, or local SQLite databases. They are excluded through `.gitignore`.

Gmail permissions use OAuth scopes appropriate to the available features. Any action that changes Gmail requires a separate confirmation step in the UI.

## Development history

- **v0.1** — desktop overlay foundation
- **v0.2** — interactive AI command surface
- **v0.3** — Gmail OAuth and read-only retrieval
- **v0.4** — AI inbox classification and summaries
- **v0.5** — confirmation-protected Gmail labels and archive actions
- **v0.6** — Windows automation tools
- **v0.7** — persistent local memory and analytics
- **v1.0.0** — unified polished desktop assistant
