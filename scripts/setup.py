"""Create isolated development configuration without overwriting existing work."""
from pathlib import Path
import secrets

def setup(root: Path):
    target = root / ".env.development"
    if target.exists():
        print("Existing .env.development preserved; no values changed.")
    else:
        text = (root / ".env.development.example").read_text(encoding="utf-8")
        for key, size in (("SOCIALSCOPE_DEV_DB_PASSWORD", 24), ("SECRET_KEY", 48), ("LOCAL_ADMIN_PASSWORD", 18)):
            text = text.replace(f"{key}=GENERATE_WITH_SETUP", f"{key}=" + secrets.token_urlsafe(size))
        with target.open("x", encoding="utf-8") as stream:
            stream.write(text)
        print("Created .env.development with independent database, signing, and admin secrets; provider keys are blank.")
    if (root / ".env").exists():
        print("Legacy .env left untouched. It is not used by the explicit development command below.")
    print("Development uses new socialscope-dev volumes; existing socialscope data is not migrated or removed.")
    print("Review .env.development privately; add provider keys only for intentional live API tests.")
    print("Then: docker compose --env-file .env.development -f compose.development.yml up --build -d")
    print("Default URL: http://localhost:3102 (use your configured port if different).")
    print("Sign in with LOCAL_ADMIN_EMAIL / LOCAL_ADMIN_PASSWORD from .env.development.")
    print("No containers, databases, or provider requests were started by setup.")


if __name__ == "__main__":
    setup(Path(__file__).resolve().parents[1])
