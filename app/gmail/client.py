"""Gmail client for AI Gmail Organizer v0.5."""

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
BASE_DIR = Path(__file__).resolve().parents[2]
CREDENTIALS_FILE = BASE_DIR / os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")
TOKEN_FILE = BASE_DIR / os.getenv("GMAIL_TOKEN_FILE", "token.json")


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

    @property
    def is_connected(self) -> bool:
        return self._service is not None

    def connect(self) -> None:
        creds: Credentials | None = None
        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif not creds or not creds.valid:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    "credentials.json was not found. Create a Google OAuth desktop "
                    "client and place the downloaded file at the project root."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        self._service = build("gmail", "v1", credentials=creds)

    def list_messages(self, query: str = "", max_results: int = 10) -> list[GmailMessage]:
        self._require_connection()
        response = (
            self._service.users().messages().list(
                userId="me", q=query or None, maxResults=max_results
            ).execute()
        )
        messages: list[GmailMessage] = []
        for item in response.get("messages", []):
            message = (
                self._service.users()
                .messages()
                .get(
                    userId="me",
                    id=item["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject"],
                )
                .execute()
            )
            headers = {
                header["name"].lower(): header.get("value", "")
                for header in message.get("payload", {}).get("headers", [])
            }
            messages.append(
                GmailMessage(
                    id=message["id"],
                    thread_id=message.get("threadId", ""),
                    sender=headers.get("from", ""),
                    subject=headers.get("subject", "(no subject)"),
                    snippet=message.get("snippet", ""),
                )
            )
        return messages

    def create_label(self, name: str) -> str:
        self._require_connection()
        response = self._service.users().labels().create(
            userId="me",
            body={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
        ).execute()
        return response["id"]

    def list_labels(self) -> list[dict[str, str]]:
        self._require_connection()
        response = self._service.users().labels().list(userId="me").execute()
        return [{"id": label["id"], "name": label["name"]} for label in response.get("labels", [])]

    def apply_label(self, message_id: str, label_id: str) -> None:
        self._require_connection()
        self._service.users().messages().modify(
            userId="me", id=message_id, body={"addLabelIds": [label_id]}
        ).execute()

    def archive_message(self, message_id: str) -> None:
        self._require_connection()
        self._service.users().messages().modify(
            userId="me", id=message_id, body={"removeLabelIds": ["INBOX"]}
        ).execute()

    def _require_connection(self) -> None:
        if not self._service:
            raise RuntimeError("Gmail is not connected. Use connect() first.")
