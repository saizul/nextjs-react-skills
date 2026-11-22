import json
import shutil

import pytest

from conftest import FIXTURES, load_script, run_script

SKILL = "nextjs-env-config"
SCRIPT = "env_audit.py"
mod = load_script(SKILL, SCRIPT)
SRC = FIXTURES / SKILL


@pytest.fixture(scope="module")
def F(tmp_path_factory):
    """Copy fixtures and restore .gitignore files (stored as gitignore.fixture so git keeps .env.local)."""
    dst = tmp_path_factory.mktemp("env") / SKILL
    shutil.copytree(SRC, dst)
    for g in dst.rglob("gitignore.fixture"):
        g.rename(g.with_name(".gitignore"))
    return dst


def rules(findings):
    return {f["rule"] for f in findings}


def test_bad_project(F):
    found = mod.audit(F / "bad")
    assert {
        "ENV001",
        "ENV002",
        "ENV003",
        "ENV004",
        "ENV005",
        "ENV006",
        "ENV007",
        "ENV008",
        "ENV010",
        "ENV011",
    } <= rules(found)
    env010 = {f["message"].split()[1]: f["severity"] for f in found if f["rule"] == "ENV010"}
    assert env010 == {"env.API_SECRET": "high", "env.BUILD_LABEL": "low"}


def test_values_are_never_printed(F):
    r = run_script(SKILL, SCRIPT, str(F / "bad"), "--json")
    for secret in ("changeme", "placeholder-value", "sk_live_x", "api.example.com"):
        assert secret not in r.stdout
    assert "NEXT_PUBLIC_STRIPE_SECRET_KEY" in r.stdout


def test_good_project_is_clean(F):
    assert mod.audit(F / "good") == []


def test_parse_env_file():
    env = mod.parse_env_file('A=1\nexport B="two words"\n# c\nC=x # comment\nD=\nnot a line\n')
    assert env == {"A": "1", "B": "two words", "C": "x", "D": ""}


def test_gitignore_matching():
    pats = [".env*", "!.env.example"]
    assert mod.is_ignored(".env.local", pats)
    assert not mod.is_ignored(".env.example", pats)
    assert mod.is_ignored(".env.production.local", [".env*.local"])
    assert not mod.is_ignored(".env", [".env*.local"])


def test_public_allowlist(tmp_path):
    (tmp_path / ".env.local").write_text(
        "NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk\nNEXT_PUBLIC_SUPABASE_ANON_KEY=anon\nNEXT_PUBLIC_GITHUB_TOKEN=t\n"
    )
    (tmp_path / ".gitignore").write_text(".env*\n")
    found = [f for f in mod.audit(tmp_path) if f["rule"] == "ENV003"]
    assert [f["message"].split(":")[0] for f in found] == ["NEXT_PUBLIC_GITHUB_TOKEN"]


def test_secret_name_used_only_in_code(tmp_path):
    (tmp_path / "a.ts").write_text("export const k = process.env.NEXT_PUBLIC_OPENAI_API_KEY\n")
    assert "ENV003" in rules(mod.audit(tmp_path))


def test_server_file_may_read_secrets(tmp_path):
    (tmp_path / "a.ts").write_text("export const k = process.env.STRIPE_SECRET_KEY\n")
    assert mod.audit(tmp_path) == []


def test_example_file_is_not_treated_as_secret(tmp_path):
    (tmp_path / ".env.example").write_text("NEXT_PUBLIC_X=\n")
    assert mod.audit(tmp_path) == []


def test_cli(F):
    assert run_script(SKILL, SCRIPT, str(F / "bad")).returncode == 1
    r = run_script(SKILL, SCRIPT, str(F / "good"), "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["findings"] == []
    assert run_script(SKILL, SCRIPT, str(F / "missing")).returncode == 2


def test_help():
    r = run_script(SKILL, SCRIPT, "--help")
    assert r.returncode == 0 and "Never prints values" in r.stdout


def test_committed_env_file_severity(tmp_path):
    (tmp_path / ".env.production").write_text("NEXT_PUBLIC_SITE_NAME=Acme\n")
    (tmp_path / ".env").write_text("FEATURE_X=1\n")
    (tmp_path / ".env.test.local").write_text("TOKEN_FOR_TESTS=x\n")
    sev = {f["file"]: f["severity"] for f in mod.audit(tmp_path) if f["rule"] == "ENV001"}
    assert sev == {".env.production": "low", ".env": "medium", ".env.test.local": "high"}
