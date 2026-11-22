import json

import pytest

from conftest import FIXTURES, load_script, run_script

SKILL = "server-actions-security"
SCRIPT = "action_scan.py"
mod = load_script(SKILL, SCRIPT)
F = FIXTURES / SKILL


def by_fn(findings):
    out = {}
    for f in findings:
        name = f["message"].split("'")[1] if "'" in f["message"] else f["file"]
        out.setdefault(name, set()).add(f["rule"])
    return out


def test_bad_actions():
    s = by_fn(mod.scan(F / "bad"))
    assert {"SA001", "SA002"} <= s["deletePost"]
    assert {"SA001", "SA002", "SA003", "SA004"} <= s["login"]
    assert {"SA002", "SA005"} <= s["updateProfile"] and "SA001" not in s["updateProfile"]
    assert s["refreshFeed"] == {"SA001"}  # no params -> no validation finding
    assert {"SA001", "SA002", "SA006"} <= s["POST"]
    assert {"SA001", "SA002"} <= s["like"]


def test_get_handler_is_ignored():
    names = by_fn(mod.scan(F / "bad"))
    assert "GET" not in names


def test_config_findings():
    rules = {f["rule"] for f in mod.scan(F / "bad")}
    assert {"SA010", "SA011"} <= rules


def test_good_is_clean():
    assert mod.scan(F / "good") == []


def test_public_marker_skips_only_auth(tmp_path):
    (tmp_path / "a.ts").write_text(
        "'use server'\n// action-scan: public\nexport async function subscribe(formData: FormData) {\n"
        "  await db.sub.create({ data: { email: formData.get('email') } })\n}\n"
    )
    rules = {f["rule"] for f in mod.scan(tmp_path)}
    assert "SA001" not in rules and {"SA002", "SA004"} <= rules


def test_marker_does_not_leak_to_next_function(tmp_path):
    (tmp_path / "a.ts").write_text(
        "'use server'\n// action-scan: public\nexport async function ping() {\n  return 1\n}\n\n\n\n"
        "export async function wipe() {\n  await db.all.delete()\n}\n"
    )
    s = by_fn(mod.scan(tmp_path))
    assert "ping" not in s and s["wipe"] == {"SA001"}


def test_extra_auth_pattern(tmp_path):
    (tmp_path / "a.ts").write_text("'use server'\nexport async function x() {\n  await mustBeLoggedIn()\n}\n")
    assert mod.scan(tmp_path)
    assert mod.scan(tmp_path, extra_auth=[r"\bmustBeLoggedIn\("]) == []


def test_arrow_and_default_exports(tmp_path):
    (tmp_path / "a.ts").write_text(
        "'use server'\nexport const a = async (id: string) => db.x.delete(id)\n"
        "export default async function (input: unknown) { return input }\n"
    )
    s = by_fn(mod.scan(tmp_path))
    assert {"SA001", "SA002"} <= s["a"] and "SA001" in s["default"]


def test_strings_with_braces_do_not_break_body(tmp_path):
    (tmp_path / "a.ts").write_text(
        "'use server'\nexport async function a(f: FormData) {\n  const s = '}'\n  const session = await auth()\n"
        "  Schema.parse(f)\n}\n"
    )
    assert mod.scan(tmp_path) == []


@pytest.mark.parametrize(
    "line,flag",
    [
        ("redirect(formData.get('next') as string)", True),
        ("redirect(searchParams.callbackUrl)", True),
        ("redirect('/dashboard')", False),
        ("redirect(`/posts/${post.id}`)", False),
    ],
)
def test_open_redirect(line, flag):
    hit = mod.USER_REDIRECT.search(line) is not None
    assert hit is flag


def test_cli():
    r = run_script(SKILL, SCRIPT, str(F / "bad"), "--json")
    assert r.returncode == 1
    assert json.loads(r.stdout)["summary"]["high"] >= 8
    assert run_script(SKILL, SCRIPT, str(F / "good")).returncode == 0
    assert run_script(SKILL, SCRIPT, str(F / "nope")).returncode == 2
    assert run_script(SKILL, SCRIPT, str(F / "bad"), "--auth-pattern", "(").returncode == 2


def test_help():
    r = run_script(SKILL, SCRIPT, "--help")
    assert r.returncode == 0 and "--auth-pattern" in r.stdout


def test_double_wildcard_origin(tmp_path):
    (tmp_path / "next.config.mjs").write_text(
        "export default { experimental: { serverActions: { allowedOrigins: ['**'] } } }\n"
    )
    assert {f["rule"] for f in mod.scan(tmp_path)} == {"SA010"}
    (tmp_path / "next.config.mjs").write_text(
        "export default { experimental: { serverActions: { allowedOrigins: ['*.example.com'] } } }\n"
    )
    assert mod.scan(tmp_path) == []
