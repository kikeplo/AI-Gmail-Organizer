# Architecture Notes

## v0.4

The application is organized into separate layers:

```text
Windows Overlay (PySide6)
        │
        ▼
   CommandAgent
   ┌────┴────────────┐
   ▼                 ▼
GmailClient     InboxClassifier
   │                 │
   ▼                 ▼
 Gmail API       AI model / local rules
```

### Inbox analysis flow

1. The user selects **Organize inbox** or enters a natural-language command.
2. `CommandAgent` ensures Gmail OAuth is connected.
3. `GmailClient` retrieves a small read-only message sample with sender, subject, and snippet metadata.
4. `InboxClassifier` classifies each message as `important`, `work`, `personal`, `promotions`, `newsletters`, or `other`.
5. With an AI key, the classifier requests structured JSON classification from the configured model. Without one, it uses deterministic local rules.
6. The classifier returns category counts and concise explanations for the top messages.

### Safety boundary

v0.4 does not modify Gmail. There are no archive, label, delete, send, or move operations. The organization feature remains read-only while the classification pipeline is validated.

### Next architectural step

v0.5 will add explicit Gmail write tools behind a confirmation layer. The agent should propose an action, show the affected messages, and wait for user approval before changing external state.
