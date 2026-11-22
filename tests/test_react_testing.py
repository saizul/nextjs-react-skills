import json

from conftest import FIXTURES, load_script, run_script

SKILL = "react-testing"
SCRIPT = "find_test_gaps.py"
mod = load_script(SKILL, SCRIPT)
F = FIXTURES / SKILL


def test_detect_setup_bad():
    setup, found = mod.detect_setup(F / "bad")
    assert setup["runner"] == "jest" and not setup["react_testing_library"]
    assert {"TST002", "TST003", "TST004", "TST005", "TST006"} <= {f["rule"] for f in found}


def test_detect_setup_good():
    setup, found = mod.detect_setup(F / "good")
    assert setup["runner"] == "vitest" and setup["user_event"] and setup["dom_env"]
    assert found == []


def test_no_runner(tmp_path):
    (tmp_path / "package.json").write_text('{"dependencies": {"react": "19.2.0"}}')
    setup, found = mod.detect_setup(tmp_path)
    assert setup["runner"] is None and [f["rule"] for f in found] == ["TST001"]


def test_vitest_without_dom_environment(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"devDependencies": {"vitest": "4", "jsdom": "27"}}))
    (tmp_path / "vitest.config.ts").write_text("export default { test: {} }\n")
    _, found = mod.detect_setup(tmp_path)
    assert any(f["rule"] == "TST003" and f["file"] == "vitest.config.ts" for f in found)


def test_gaps_bad():
    gaps = mod.gaps(F / "bad", include_routes=False)
    assert [g["file"] for g in gaps] == ["components/Modal.tsx", "hooks/useCart.ts", "components/Button.tsx"]
    assert gaps[1]["kind"] == "hook"


def test_routes_included_on_request():
    files = [g["file"] for g in mod.gaps(F / "bad", include_routes=True)]
    assert "app/page.tsx" in files


def test_gaps_good_index_and_dunder_tests():
    assert mod.gaps(F / "good", include_routes=False) == []


def test_smells():
    setup, _ = mod.detect_setup(F / "bad")
    rules = {f["rule"] for f in mod.smells(F / "bad", setup)}
    assert {"TST010", "TST011", "TST012", "TST013", "TST015"} <= rules
    assert "TST014" not in rules  # user-event is not installed


def test_fireevent_with_user_event(tmp_path):
    (tmp_path / "a.test.tsx").write_text("fireEvent.click(btn); expect(x).toBe(1)\n" + "getByTestId('a');" * 5)
    rules = {f["rule"] for f in mod.smells(tmp_path, {"user_event": True})}
    assert rules == {"TST014", "TST016"}


def test_cli():
    r = run_script(SKILL, SCRIPT, str(F / "bad"))
    assert r.returncode == 1 and "components/Modal.tsx" in r.stdout
    r = run_script(SKILL, SCRIPT, str(F / "good"), "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["untested_total"] == 0
    r = run_script(SKILL, SCRIPT, str(F / "bad"), "--fail-on", "low", "--json", "--top", "1")
    data = json.loads(r.stdout)
    assert r.returncode == 1 and len(data["untested"]) == 1 and data["untested_total"] == 3
    assert run_script(SKILL, SCRIPT, str(F / "nope")).returncode == 2


def test_help():
    r = run_script(SKILL, SCRIPT, "--help")
    assert r.returncode == 0 and "--include-routes" in r.stdout
