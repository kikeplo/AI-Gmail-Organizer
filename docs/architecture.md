# Architecture Notes

## v0.1

The application is a Python desktop application using PySide6. The UI is intentionally separated from future agent, Gmail, Windows automation, and database modules.

### Why start with a shell?

The overlay is the interaction surface for the eventual assistant. Building it first gives us a stable place to plug in an AI agent without coupling the UI to provider-specific code.

### Next architectural step

Introduce an `agent` service that receives a user command and returns a structured response. The agent will eventually be able to request tools such as:

- `gmail.search_messages`
- `gmail.get_message`
- `gmail.archive_message`
- `gmail.apply_label`
- `windows.active_window`

Destructive or externally visible actions should require confirmation from the user unless explicitly configured otherwise.
