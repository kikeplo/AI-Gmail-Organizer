# AI Gmail Organizer — Portable Windows distribution

The application is distributed as a folder rather than a single EXE file.

## For the developer

Run:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_portable_windows.ps1
```

The build produces:

```text
dist\AI-Gmail-Organizer\
├── AI-Gmail-Organizer.exe
├── playwright\
├── *.dll / packaged Python runtime files
└── other packaged application components
```

The build script stops if the launcher, Playwright runtime, Chromium browser, or core desktop automation packages were not packaged.

## For the end user

Copy or extract the entire `AI-Gmail-Organizer` folder. Do not move only the EXE out of the folder.

Launch:

```text
AI-Gmail-Organizer.exe
```

The folder contains the runtime components needed by the application. The user should not need to install Python, pip, PyAutoGUI, pywinauto, or Playwright separately.

The user still needs to configure their own Gmail account and AI provider/API credentials inside the application.
