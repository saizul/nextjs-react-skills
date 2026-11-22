import json

import pytest

from conftest import FIXTURES, load_script, run_script

SKILL = "nextjs-app-router-patterns"
SCRIPT = "rsc_boundary_check.py"
mod = load_script(SKILL, SCRIPT)
F = FIXTURES / SKILL


def rules(findings):
    return {(f["rule"], f["file"]) for f in findings}


def test_bad_project_findings():
    r = rules(mod.check_project(F / "bad"))
    assert ("RSC001", "app/page.tsx") in r
    assert ("RSC002", "app/error.tsx") in r
    assert ("RSC003", "app/layout.tsx") in r
    assert ("RSC004", "components/Widget.tsx") in r
    assert ("RSC005", "components/Widget.tsx") in r
    assert ("RSC006", "components/Widget.tsx") in r
    assert ("RSC008", "app/blog/[slug]/page.tsx") in r
    assert ("RSC011", "app/actions.ts") in r
    assert ("RSC012", "app/dashboard/@analytics") in r
    assert ("RSC013", "middleware.ts") in r


def test_sync_params_and_cookies_are_both_reported():
    msgs = [f["message"] for f in mod.check_project(F / "bad") if f["rule"] == "RSC008"]
    assert any("cookies()" in m for m in msgs)
    assert any("params" in m for m in msgs)


def test_good_project_is_clean():
    assert mod.check_project(F / "good") == []
    assert mod.check_project(F / "good", strict=True) == []


def test_strict_reports_implicit_client_module():
    normal = rules(mod.check_project(F / "bad"))
    strict = rules(mod.check_project(F / "bad", strict=True))
    assert ("RSC010", "components/Counter.tsx") not in normal
    assert ("RSC010", "components/Counter.tsx") in strict


def test_comments_do_not_trigger(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "page.tsx").write_text(
        "// const [x] = useState(0)\n/* <button onClick={go}> */\nexport default function P() { return <p>hi</p> }\n"
    )
    assert mod.check_project(tmp_path) == []


def test_directive_detection():
    assert mod.directive("'use client'\nimport x") == "client"
    assert mod.directive('\n\n"use server";\n') == "server"
    assert mod.directive("import x\n'use client'") is None
    assert mod.directive("'use strict';\n'use client'") == "client"


@pytest.mark.parametrize(
    "code,expected",
    [
        ("revalidateTag('posts')", True),
        ("revalidateTag(`user-${id}`)", True),
        ("revalidateTag('posts', 'max')", False),
        ("revalidateTag(tag, { expire: 60 })", False),
    ],
)
def test_revalidate_tag_arity(tmp_path, code, expected):
    (tmp_path / "a.ts").write_text(f"'use server'\nexport async function x() {{ {code} }}\n")
    found = any(f["rule"] == "RSC011" for f in mod.check_project(tmp_path))
    assert found is expected


def test_awaited_params_not_flagged(tmp_path):
    page = tmp_path / "app" / "[id]" / "page.tsx"
    page.parent.mkdir(parents=True)
    page.write_text(
        "export default async function P(props: { params: Promise<{ id: string }> }) {\n"
        "  const params = await props.params\n  return <p>{params.id}</p>\n}\n"
    )
    assert mod.check_project(tmp_path) == []


def test_src_app_layout_is_found(tmp_path):
    app = tmp_path / "src" / "app"
    app.mkdir(parents=True)
    (app / "error.tsx").write_text("export default function E() { return null }\n")
    assert rules(mod.check_project(tmp_path)) == {("RSC002", "src/app/error.tsx")}


def test_cli_json_and_exit_codes():
    r = run_script(SKILL, SCRIPT, str(F / "bad"), "--json")
    assert r.returncode == 1
    data = json.loads(r.stdout)
    assert data["summary"]["high"] >= 8
    assert run_script(SKILL, SCRIPT, str(F / "good")).returncode == 0
    assert run_script(SKILL, SCRIPT, str(F / "bad"), "--fail-on", "high").returncode == 1
    assert run_script(SKILL, SCRIPT, str(F / "nope")).returncode == 2


def test_cli_single_file():
    r = run_script(SKILL, SCRIPT, str(F / "bad" / "components" / "Widget.tsx"))
    assert r.returncode == 1 and "RSC005" in r.stdout


def test_help():
    r = run_script(SKILL, SCRIPT, "--help")
    assert r.returncode == 0 and "--strict" in r.stdout
