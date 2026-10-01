"""Create private pilot configuration without overwriting existing work."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    print("Existing .env preserved. Review its provider keys and local login settings.")
else:
    text = (root / ".env.example").read_text(encoding="utf-8")
    text = text.replace("SECRET_KEY=change-me-in-production", "SECRET_KEY=" + secrets.token_urlsafe(48))
    text = text.replace("LOCAL_ADMIN_PASSWORD=password123", "LOCAL_ADMIN_PASSWORD=" + secrets.token_urlsafe(18))
    with target.open("x", encoding="utf-8") as stream:
        stream.write(text)
    print("Created .env with a random signing secret and local admin password.")
print("Privately edit .env: add the administrator's shared SociaVault/Xpoz keys.")
print("Then: docker compose up --build -d")
print("Open http://localhost:3002 and sign in using LOCAL_ADMIN_EMAIL / LOCAL_ADMIN_PASSWORD in .env.")
print("No provider requests have been made by this setup script.")
