from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_runtime_code_never_creates_schema_outside_alembic():
    main_source = (PROJECT_ROOT / "backend" / "app" / "main.py").read_text()
    seed_source = (PROJECT_ROOT / "backend" / "app" / "seed.py").read_text()

    assert "metadata.create_all" not in main_source
    assert "metadata.create_all" not in seed_source


def test_compose_runs_migrations_before_seed_and_backend():
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text()
    seed_block = compose.split("  seed:\n", 1)[1].split("\n  backend:\n", 1)[0]
    backend_block = compose.split("  backend:\n", 1)[1].split("\n  worker:\n", 1)[0]

    assert "  migrate:\n" in compose
    assert "command: alembic upgrade head" in compose
    assert "migrate:" in seed_block
    assert "condition: service_completed_successfully" in seed_block
    assert "migrate:" in backend_block
    assert "condition: service_completed_successfully" in backend_block
    assert compose.index("  migrate:\n") < compose.index("  seed:\n")
    assert compose.index("  migrate:\n") < compose.index("  backend:\n")
