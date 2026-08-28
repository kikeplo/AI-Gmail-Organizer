# Architecture Notes

## v0.7

The application now adds a local memory boundary alongside Gmail and Windows automation. The UI remains responsible for presentation and confirmation; the command agent routes requests to typed services.

```text
                         Windows Overlay
                              │
                              ▼
                         CommandAgent
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
              Gmail tools  Windows   MemoryStore
                    │         │         │
                    ▼         ▼         ▼
                Gmail API  pywin32   SQLite file
```

### Local memory

`MemoryStore` keeps lightweight interaction records locally:

- command text
- response text
- response mode
- UTC timestamp

The SQLite database is created under `data/assistant.db` by default and is excluded from version control.

The agent exposes simple local queries for recent history and aggregate usage statistics. This is intentionally lightweight: v0.7 does not upload memory to a hosted service or treat email contents as a global training store.

### Safety boundary

Gmail write operations remain confirmation-protected. Windows automation remains limited to explicit supported window-management operations. Local memory is stored on the user's machine.

## v1.0 direction

The final milestone should unify Gmail, Windows automation, local memory, and the AI tool interface into a polished desktop assistant with clear permissions, better error handling, and production-quality UX.
