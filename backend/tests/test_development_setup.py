"""Safe development setup checks using temporary folders, never real credentials."""
from pathlib import Path
from types import SimpleNamespace
import runpy
import subprocess

ROOT = Path(__file__).resolve().parents[2]
setup = runpy.run_path(str(ROOT / "scripts/setup.py"))["setup"]


def parse_env(text):
    return dict(line.split("=", 1) for line in text.splitlines() if line and not line.startswith("#") and "=" in line)


def test_setup_generates_independent_development_secrets_without_touching_legacy_or_prod(tmp_path, capsys):
    (tmp_path / ".env.development.example").write_text((ROOT / ".env.development.example").read_text(encoding="utf-8"), encoding="utf-8")
    legacy = b"PRIVATE_LEGACY_CONFIGURATION=leave-unchanged\n"
    production = b"PRIVATE_PRODUCTION_CONFIGURATION=leave-unchanged\n"
    (tmp_path / ".env").write_bytes(legacy)
    (tmp_path / ".env.production").write_bytes(production)
    setup(tmp_path)
    values = parse_env((tmp_path / ".env.development").read_text(encoding="utf-8"))
    keys = ("SOCIALSCOPE_DEV_DB_PASSWORD", "SECRET_KEY", "LOCAL_ADMIN_PASSWORD")
    secrets = [values[key] for key in keys]
    assert len(set(secrets)) == 3 and all(len(value) >= 24 for value in secrets)
    assert all("GENERATE_WITH_SETUP" not in value for value in secrets)
    assert values["LOCAL_ADMIN_EMAIL"] == "admin@socialscope-dev.local"
    assert values["SOCIALVAULT_API_KEY"] == values["XPOZ_API_KEY"] == values["OPENAI_API_KEY"] == ""
    assert "DATABASE_URL" not in values
    assert (tmp_path / ".env").read_bytes() == legacy
    assert (tmp_path / ".env.production").read_bytes() == production
    output = capsys.readouterr().out
    assert all(secret not in output for secret in secrets)
    assert "--env-file .env.development -f compose.development.yml" in output


def test_existing_development_settings_are_preserved(tmp_path, capsys):
    existing = b"KEEP_MY_SETTINGS=exactly\n"
    (tmp_path / ".env.development").write_bytes(existing)
    setup(tmp_path)
    assert (tmp_path / ".env.development").read_bytes() == existing
    assert "preserved" in capsys.readouterr().out


def test_connectivity_discovery_explicitly_selects_development(monkeypatch):
    calls = []
    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout="127.0.0.1:3102\n")
    monkeypatch.setattr(subprocess, "run", fake_run)
    helper = runpy.run_path(str(ROOT / "scripts/check-connectivity.py"))
    assert helper["published_url"]("frontend", 3001) == "http://127.0.0.1:3102"
    assert calls[0][0] == ["docker", "compose", "--env-file", ".env.development", "-f", "compose.development.yml", "port", "frontend", "3001"]
    assert calls[0][1]["cwd"] == ROOT
