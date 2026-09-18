# AI Gmail Organizer

**Current version: v3.14.5**

Hybrid Windows desktop assistant for Gmail organization, natural-language desktop automation, local AI, browser automation, vision-assisted interaction, reusable skills, learned procedures, autonomous task planning, and explicit access permissions.

## Features

### Gmail
- OAuth 2.0 authentication
- Search unread, starred, recent, and sender-specific messages
- Inbox classification and summaries
- Create and apply Gmail labels
- Archive messages
- Confirmation before Gmail actions that change mailbox state
- Gmail API actions for fast, deterministic mailbox operations

### Windows and desktop automation
- Inspect the active window
- Minimize, maximize, and restore the active window
- Natural-language file and folder opening across common Windows locations
- Controlled mouse, keyboard, scrolling, hotkeys, and window interaction
- Browser and vision-assisted UI interaction when deterministic controls are insufficient
- Explicit desktop access permissions for screen, input, and browser capabilities
- No arbitrary shell-command execution through the natural-language interface

### Local assistant and AI
- Natural-language command interface
- Local Ollama AI with a fast Qwen3 text model (`qwen3:1.7b`) and a quality model (`qwen3:4b`)
- Local Qwen3-VL vision model for screenshot-based interaction (`qwen3-vl:2b`)
- Local-only routing mode for keeping AI processing on the machine
- Local-first/cloud-first/balanced routing with complexity-aware Cloud AI escalation when allowed
- Optional Cloud AI reassessment after a thumbs-down on an AI-generated answer
- Optional OpenAI Responses API integration
- Local interaction history and usage statistics in SQLite
- Deterministic fallbacks when external AI services are unavailable or not configured

### Browser automation
- Playwright integration
- Portable Windows packaging with Chromium included in the build

### Reliability and safety
- Background execution with live working status
- Safe cancellation for visual tasks so late model results do not execute stale desktop actions
- Confirmation gates for mutating Gmail operations
- Per-user local configuration and data storage
- Credentials, API keys, OAuth tokens, and local databases kept outside source control and the distributed application package

## Desktop application

The project can be built as a standalone Windows application. User credentials and API keys are not bundled into the application.

On first launch, the app can collect optional AI settings and a Google OAuth client file. These are stored in the current Windows user's application-data directory under `%LOCALAPPDATA%\\AI Gmail Organizer`.

Each Windows user has a separate configuration directory, OAuth token, API key configuration, and local SQLite database.

## Run from source

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
```

Install the project with development dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Start the application:

```powershell
python main.py
```

## Build locally

After installing the development dependencies, build the executable:

```powershell
.\\.venv\\Scripts\\python.exe -m PyInstaller "packaging\\AI-Gmail-Organizer.spec" --clean --noconfirm
```

The portable application folder is produced at:

```text
dist\\AI-Gmail-Organizer\\
```

and the executable is:

```text
dist\\AI-Gmail-Organizer\\AI-Gmail-Organizer.exe
```

The repository also contains a GitHub Actions Windows build that runs the automated test suite, builds the portable application, verifies the packaged executable and bundled Chromium, runs a packaged smoke test, creates a ZIP archive, and uploads the build artifact.

## Example commands

```text
Organize my inbox
Find unread Gmail emails
Archive my unread Gmail emails
Label my unread Gmail emails Work
Open the PDF on my desktop called report.pdf
Open the folder called Projects
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
                              │
                 ┌────────────┼─────────────┐
                 ▼            ▼             ▼
            Gmail tools   Windows tools   Browser/Vision
                 │            │             │
                 ▼            ▼             ▼
             Gmail API   pywin32/UI     Playwright/VL
                 │
             OAuth 2.0

                         Smart AI Router
                    ┌────────────┴────────────┐
                    ▼                         ▼
              Local Ollama                Cloud AI
              Qwen3 / Qwen3-VL          Optional fallback
                    │
                 SQLite
              local memory
```

The UI handles presentation, status, and confirmation. The command layer routes requests to deterministic Gmail, Windows, browser, and local-memory services. AI is used where interpretation or visual grounding is needed rather than for every deterministic action. Gmail mutations are confirmation-protected, desktop automation is permission-gated, Local-only mode prevents cloud escalation, and arbitrary shell commands are not exposed through the natural-language interface.

## Setup for source checkout

### Gmail

1. Enable the Gmail API in Google Cloud.
2. Create an OAuth client for a Desktop app.
3. Start the application and use the first-run setup dialog to select the downloaded OAuth JSON file.
4. Complete Google's browser authorization flow when you first use a Gmail command.

The OAuth client file and resulting token are copied to the current user's local application-data directory and are not part of the repository.

### Local AI

Install Ollama separately, then use the application's Local AI settings to check availability and install the required local models. The default text model is `qwen3:1.7b`; the optional quality model is `qwen3:4b`; visual tasks use `qwen3-vl:2b`.

Local AI can be used without a cloud API key. Select Local-only routing when cloud escalation should be disabled.

### Cloud AI (optional)

The first-run setup dialog can save an OpenAI API key and model name to the current user's local configuration. When enabled in Settings, a thumbs-down on a general AI reply can send that prompt and response to the configured Cloud AI provider for a second assessment and improved answer. The repository only contains `.env.example` with empty placeholders.

## Testing

Run the test suite locally with:

```powershell
.\\.venv\\Scripts\\python.exe -m pytest -q
```

GitHub Actions runs the same pytest suite on Windows before producing the portable package. The packaged smoke test additionally verifies the built executable, bundled Chromium, Playwright startup, and packaged runtime dependencies.

## Security

Never commit API keys, OAuth credentials, OAuth tokens, `.env` files containing secrets, or local databases. `.gitignore` excludes the standard secret and local-data files.

The distributed application is the same code for every user; user-specific credentials remain outside the application package and outside source control.

## Development history

### Foundation
- **v0.1** — desktop overlay foundation
- **v0.2** — interactive command interface
- **v0.3** — Gmail OAuth and read-only retrieval
- **v0.4** — inbox classification and summaries
- **v0.5** — confirmed Gmail labels and archive actions
- **v0.6** — Windows automation tools
- **v0.7** — local memory and usage analytics
- **v1.0.0** — unified desktop assistant foundation

### Expansion and platform hardening
- **v1.x–v2.x** — expanded the assistant beyond the original Gmail workflow with browser automation, reusable skills, learned procedures, task planning, broader Windows controls, provider integration, permissions, and deployment tooling
- **v3.0–v3.8** — matured the hybrid desktop-assistant architecture, strengthening automation, browser/vision capabilities, provider failover, setup flows, permissions, and portable Windows deployment
- **v3.8.3** — consolidated the mature desktop-assistant architecture with explicit desktop permissions, automation, browser/vision capabilities, provider and deployment improvements

### Local AI and production refinement
- **v3.12** — introduced the local-AI architecture built around Ollama, with local/cloud routing and a dedicated local execution path
- **v3.13.0–v3.13.1** — expanded Local AI settings and routing controls and continued performance/refinement work
- **v3.13.2** — tuned local inference for responsiveness with keep-alive, context, and generation-budget controls
- **v3.13.3** — improved local-model installation reliability and established the fast Qwen3 model as the default local text path
- **v3.13.4** — refined model-installation progress, status feedback, and error presentation
- **v3.13.5** — improved visual-task responsiveness and background execution feedback
- **v3.13.6** — further optimized local text and vision inference for practical desktop use
- **v3.13.7** — added more universal natural-language Windows file and folder commands
- **v3.13.8** — release hardening: synchronized version metadata and documentation, expanded release documentation, and CI unit-test coverage
- **v3.13.9** — desktop automation fixes: safer vision coordinate mapping, stronger natural-language file/folder resolution, latest-file opening, and deterministic Windows Start-button handling
- **v3.14.0** — expanded general-purpose conversation with complexity-aware local/cloud routing, recent conversation context, ChatGPT-style thumbs-up/thumbs-down feedback, and optional Cloud AI reassessment for unhelpful answers
- **v3.14.1** — improved conversational file commands, normalized common Downloads/Documents/Desktop locations including common typos, and fixed Local-only routing to invoke the local engine directly
- **v3.14.2** — hardened the PyInstaller package by explicitly bundling Windows automation modules required at startup
- **v3.14.3** — converted the application and subpackages to explicit Python packages to prevent frozen-runtime namespace import failures
- **v3.14.4** — collects the local `app` package as external `.pyc` modules in the portable build to avoid PYZ import-resolution failures
- **v3.14.5** — uses a filesystem-based Python module layout for the onedir package and adds a smoke-test check for `app/windows/action_router.pyc`
