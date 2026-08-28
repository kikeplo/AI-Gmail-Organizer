# AI Gmail Organizer

Windows desktop assistant for Gmail organization, window controls, and local productivity workflows.

## Features

### Gmail
- OAuth 2.0 authentication
- Search unread, starred, recent, and sender-specific messages
- Inbox classification and summaries
- Create and apply Gmail labels
- Archive messages
- Confirmation before actions that change Gmail

### Windows
- Inspect the active window
- Minimize, maximize, and restore the active window
- Small explicit automation surface rather than arbitrary shell commands

### Local assistant
- Natural-language command interface
- Optional OpenAI Responses API integration
- Local interaction history in SQLite
- Usage statistics
- Deterministic fallbacks when external AI services are not configured

## Desktop application

The project can be built as a standalone Windows executable. The executable contains the application and its dependencies, but it does **not** contain user credentials or API keys.

On first launch, the app can collect the user's optional AI settings and Google OAuth client file. These are stored in the current Windows user's application-data directory under `%LOCALAPPDATA%\\AI Gmail Organizer`.

Each Windows user has a separate configuration directory, OAuth token, API key configuration, and local SQLite database.

### Build locally

Install the project and PyInstaller:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

Build the executable:

```powershell
pyinstaller packaging/AI-Gmail-Organizer.spec --clean --noconfirm
```

The result is:

```text
dist\\AI-Gmail-Organizer.exe
```

GitHub Actions also includes a Windows build workflow that can produce the executable as a downloadable build artifact.

## Example commands

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
                  ┌───────────┼────────────┐
                  ▼           ▼            ▼
             Gmail tools  Windows tools  Local memory
                  │           │            │
                  ▼           ▼            ▼
             Gmail API     pywin32       SQLite
                  │
             OAuth 2.0

                       Optional AI provider
                              │
                              ▼
                     OpenAI Responses API
```

The UI handles presentation and confirmation. The command layer routes requests to the Gmail, Windows, and local-memory services. Gmail mutations are confirmation-protected, and arbitrary shell commands are not exposed through the natural-language interface.

## Setup for source checkout

### Gmail

1. Enable the Gmail API in Google Cloud.
2. Create an OAuth client for a Desktop app.
3. Start the application and use the first-run setup dialog to select the downloaded OAuth JSON file.
4. Complete Google's browser authorization flow when you first use a Gmail command.

The OAuth client file and resulting token are copied to the current user's local application-data directory and are not part of the repository.

### AI provider (optional)

The first-run setup dialog can save an OpenAI API key and model name to the current user's local configuration. The repository only contains `.env.example` with empty placeholders.

## Security

Never commit API keys, OAuth credentials, OAuth tokens, `.env` files containing secrets, or local databases. `.gitignore` excludes the standard secret and local-data files.

The distributed executable is the same application code for every user; user-specific credentials remain outside the executable and outside source control.

## Development history

- **v0.1** — desktop overlay foundation
- **v0.2** — interactive command interface
- **v0.3** — Gmail OAuth and read-only retrieval
- **v0.4** — inbox classification and summaries
- **v0.5** — confirmed Gmail labels and archive actions
- **v0.6** — Windows automation tools
- **v0.7** — local memory and usage analytics
- **v1.0.0** — unified desktop assistant
