# Architecture Notes

## v0.2

The application now has three clear layers:

```text
PySide6 Overlay
      │
      ▼
CommandAgent
      │
      ├── Local demo mode
      └── OpenAI Responses API

Future tools
      ├── Gmail API
      └── Windows automation
```

The UI sends plain-language commands to `CommandAgent`. The agent returns a structured `AgentResponse`, keeping provider-specific logic outside the UI.

### Safety boundary

v0.2 only produces responses. It does not claim to have performed Gmail or Windows actions. Future tools should distinguish between read operations and state-changing operations, with confirmation required for destructive or externally visible actions.

### Next architectural step

Add a Gmail service with OAuth and read-only message retrieval first. Once that is stable, introduce tool calling so natural-language commands can map to capabilities such as:

- `gmail.search_messages`
- `gmail.get_message`
- `gmail.archive_message`
- `gmail.apply_label`
- `windows.active_window`
