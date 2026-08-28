# Architecture Notes

## v0.3

The application now has a real Gmail integration boundary while keeping provider-specific behavior outside the UI layer.

```text
Windows Overlay (PySide6)
        │
        ▼
   CommandAgent
      │      │
      │      └── Optional OpenAI Responses API
      │
      ▼
   GmailClient
      │
      ├── Google OAuth 2.0
      ├── Local token persistence
      └── Gmail API (read-only)
```

### Gmail security boundary

The current OAuth scope is `gmail.readonly`. The application can retrieve message metadata and snippets, but v0.3 does not archive, label, delete, send, or otherwise modify messages.

`credentials.json` and `token.json` are local-only and excluded by `.gitignore`.

### Command routing

The command agent first recognizes simple Gmail search intents such as:

- unread mail → `is:unread`
- starred mail → `is:starred`
- sender search → `from:address@example.com`

General natural-language requests can still be routed to the optional AI provider.

## Next architectural step

v0.4 should introduce a structured tool interface so the AI model can choose among typed tools instead of relying on keyword routing. Tool execution should return structured results to the UI and preserve an explicit confirmation boundary for actions that modify external state.
