import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from pathlib import Path

BASE = Path(__file__).resolve().parent
TOKEN_FILE = BASE / "token.json"

creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
if not creds.valid:
    creds.refresh(Request())
service = build("gmail", "v1", credentials=creds)

for label in ["TRASH", "SPAM", "INBOX", "DRAFT"]:
    res = service.users().messages().list(userId="me", labelIds=[label], maxResults=500).execute()
    msgs = res.get("messages", [])
    next_page = res.get("nextPageToken")
    print(f"{label}: {len(msgs)} mensagens listadas (página 1) | resultSizeEstimate={res.get('resultSizeEstimate',0)} | tem mais paginas: {bool(next_page)}")
    for m in msgs[:3]:
        det = service.users().messages().get(userId="me", id=m["id"], format="metadata",
                                             metadataHeaders=["Subject", "From", "Date"]).execute()
        hdrs = {h["name"].lower(): h["value"] for h in det.get("payload", {}).get("headers", [])}
        print(f"    - {hdrs.get('subject','')[:50]} | {hdrs.get('from','')[:40]} | {hdrs.get('date','')[:25]}")
    print()

# Total de todas as mensagens
total_all = 0
page = None
while True:
    res = service.users().messages().list(userId="me", maxResults=500, pageToken=page).execute()
    total_all += len(res.get("messages", []))
    page = res.get("nextPageToken")
    if not page:
        break
print(f"TOTAL DE TODAS AS MENSAGENS (todas as pastas): {total_all}")
