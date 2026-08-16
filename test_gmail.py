import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gennie import get_gmail_service, listar_emails

service = get_gmail_service()
emails = listar_emails(service, query="in:inbox is:unread", max_results=5)
for e in emails:
    marca = "NAO LIDO" if e["unread"] else "lido"
    print(f"[{marca}] {e['id']} | {e['subject']} | De: {e['from']} | {e['date']}")
print("\n--- OK: acesso ao Gmail funcionando ---")
