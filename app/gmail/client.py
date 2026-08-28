"""Gmail integration and controlled inbox operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


def app_data_dir() -> Path:
    root = os.getenv("LOCALAPPDATA")
    path = Path(root) / "AI Gmail Organizer" if root else Path.home() / ".ai-gmail-organizer"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(frozen=True)
class GmailMessage:
    id: str
    thread_id: str
    sender: str = ""
    subject: str = ""
    snippet: str = ""


class GmailClient:
    """Handle Gmail OAuth and controlled inbox operations."""

    def __init__(self) -> None:
        self._service: Resource | None = None
        self.config_dir = app_data_dir()
        self.credentials_file = self.config_dir / os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")
        self.token_file = self.config_dir / os.getenv("GMAIL_TOKEN_FILE", "token.json")

    @property
    def is_connected(self) -> bool:
        return self._service is not None

    def connect(self) -> None:
        creds: Credentials | None = None
        if self.token_file.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif not creds or not creds.valid:
            # Preferred desktop-app flow: a browser opens Google's normal
            # sign-in/consent screen. A client ID can be supplied without
            # making the user browse for a JSON file.
            client_id = os.getenv("GMAIL_CLIENT_ID", "").strip()
            client_secret = os.getenv("GMAIL_CLIENT_SECRET", "").strip()
            if client_id:
                client_config = {
                    "installed": {
                        "client_id": client_id,
                        "client_secret": client_secret or "",
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["http://localhost"],
                    }
                }
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            elif self.credentials_file.exists():
                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_file), SCOPES)
            else:
                raise FileNotFoundError(
                    "Google sign-in is not configured. Set GMAIL_CLIENT_ID for the browser sign-in flow "
                    "or place a Google OAuth desktop credentials.json in the app data folder."
                )
            creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
        self.token_file.write_text(creds.to_json(), encoding="utf-8")
        self._service = build("gmail", "v1", credentials=creds)

    def list_messages(self, query: str = "", max_results: int = 10) -> list[GmailMessage]:
        self._require_connection()
        response = self._service.users().messages().list(
            userId="me", q=query or None, maxResults=max_results
        ).execute()
        messages: list[GmailMessage] = []
        for item in response.get("messages", []):
            message = self._service.users().messages().get(
                userId="me", id=item["id"], format="metadata", metadataHeaders=["From", "Subject"]
            ).execute()
            headers = {h["name"].lower(): h.get("value", "") for h in message.get("payload", {}).get("headers", [])}
            messages.append(GmailMessage(
                id=message["id"], thread_id=message.get("threadId", ""),
                sender=headers.get("from", ""), subject=headers.get("subject", "(no subject)"),
                snippet=message.get("snippet", ""),
            ))
        return messages

    def create_label(self, name: str) -> str:
        self._require_connection()
        response = self._service.users().labels().create(userId="me", body={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}).execute()
        return response["id"]

    def list_labels(self) -> list[dict[str, str]]:
        self._require_connection()
        response = self._service.users().labels().list(userId="me").execute()
        return [{"id": label["id"], "name": label["name"]} for label in response.get("labels", [])]

    def apply_label(self, message_id: str, label_id: str) -> None:
        self._require_connection()
        self._service.users().messages().modify(userId="me", id=message_id, body={"addLabelIds": [label_id]}).execute()

    def archive_message(self, message_id: str) -> None:
        self._require_connection()
        self._service.users().messages().modify(userId="me", id=message_id, body={"removeLabelIds": ["INBOX"]}).execute()

    def _require_connection(self) -> None:
        if not self._service:
            raise RuntimeError("Gmail is not connected. Use Connect Google first.")
