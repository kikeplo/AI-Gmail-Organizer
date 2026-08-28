# Architecture Notes

## v0.6

The application now exposes two automation boundaries: Gmail tools and Windows tools. The UI remains responsible for presentation and user confirmation, while the command agent routes explicit intents to typed service layers.

```text
                     Windows Overlay (PySide6)
                              │
                              ▼
                         CommandAgent
                       ┌──────┴───────┐
                       ▼              ▼
                 Gmail services   WindowsActionRouter
                       │              │
                       ▼              ▼
                  Gmail API       WindowsTools
                       │              │
                OAuth + modify     pywin32
```

### Windows automation boundary

`WindowsTools` currently provides:

- foreground/active window metadata
- minimize active window
- maximize active window
- restore active window

The implementation is explicitly guarded to Windows. The router returns a clear unavailable/error mode on other platforms rather than pretending that a desktop action ran.

### Command routing

The `CommandAgent` checks for supported Windows intents before Gmail actions and general AI responses. This gives deterministic commands a predictable path even when no external AI key is configured.

### Safety boundary

Gmail write operations remain confirmation-protected. Windows automation is limited to the explicit window-management tool set; arbitrary shell commands are not exposed through the natural-language interface.

## Next architectural step

v0.7 should introduce persistent local state for user preferences, action history, and lightweight analytics. The final v1.0 can then combine Gmail workflows, Windows automation, and a polished agent/tool interface behind clear permission boundaries.
