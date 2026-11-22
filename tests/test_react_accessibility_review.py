import json

import pytest

from conftest import FIXTURES, load_script, run_script

SKILL = "react-accessibility-review"
SCRIPT = "a11y_scan.py"
mod = load_script(SKILL, SCRIPT)
F = FIXTURES / SKILL


def rules_of(code):
    return [f["rule"] for f in mod.scan_code(mod.strip_comments(code), "x.tsx")]


def test_bad_fixture():
    found = mod.scan(F / "bad")
    lines = {(f["rule"], f["line"]) for f in found}
    expected = {
        ("A11Y001", 8),
        ("A11Y001", 9),
        ("A11Y002", 10),
        ("A11Y003", 11),
        ("A11Y004", 12),
        ("A11Y005", 12),
        ("A11Y006", 13),
        ("A11Y006", 14),
        ("A11Y007", 15),
        ("A11Y007", 18),
        ("A11Y008", 19),
        ("A11Y008", 20),
        ("A11Y009", 21),
        ("A11Y010", 21),
        ("A11Y011", 22),
        ("A11Y013", 23),
        ("A11Y012", 3),
    }
    assert expected <= lines


def test_good_fixture_is_clean():
    assert mod.scan(F / "good") == []


@pytest.mark.parametrize(
    "code,rule",
    [
        ("const a = <img src='x' />", "A11Y001"),
        ('const a = <input type="image" src="go.png" />', "A11Y001"),
        ("const a = <li onClick={go}>x</li>", "A11Y003"),
        ('const a = <a href="javascript:void(0)" onClick={go}>x</a>', "A11Y006"),
        ("const a = <button><svg /></button>", "A11Y007"),
        ("const a = <textarea name='m' />", "A11Y008"),
        ('const a = <div tabIndex="2">x</div>', "A11Y009"),
        ("const a = <a href='/x' aria-hidden='true'>x</a>", "A11Y011"),
    ],
)
def test_single_rules(code, rule):
    assert rule in rules_of(code)


@pytest.mark.parametrize(
    "code",
    [
        "const a = <button>{label}</button>",
        "const a = <button aria-label='Close'><X /></button>",
        "const a = <img {...props} />",
        "const s = useState<string>('')",
        "const m = new Map<string, number>()",
        "const a = <label>Name <input name='n' /></label>",
        "const a = <><label htmlFor='n'>Name</label><input id='n' /></>",
        "const a = <input type='submit' value='Go' />",
        "const a = <div onClick={() => x > 1 && go()} role='button' tabIndex={0} onKeyDown={k}>x</div>",
        "// <img src='x' />",
        "const a = <p>Click <a href='/docs'>here</a> for more</p>",
    ],
)
def test_no_false_positives(code):
    assert rules_of(code) == []


def test_parse_attrs():
    attrs, spreads = mod.parse_attrs(' src="/a.png" alt={t("x")} hidden {...rest} data-x=\'1\' /')
    assert attrs == {"src": "/a.png", "alt": '{t("x")}', "hidden": True, "data-x": "1"}
    assert spreads == ["rest"]


def test_register_spread_still_needs_label():
    assert "A11Y008" in rules_of("const a = <input {...register('email')} />")


def test_cli():
    r = run_script(SKILL, SCRIPT, str(F / "bad"), "--json")
    assert r.returncode == 1 and json.loads(r.stdout)["summary"]["high"] >= 8
    assert run_script(SKILL, SCRIPT, str(F / "good")).returncode == 0
    assert run_script(SKILL, SCRIPT, str(F / "bad" / "components" / "Bad.tsx")).returncode == 1
    assert run_script(SKILL, SCRIPT, str(F / "none")).returncode == 2


def test_help():
    r = run_script(SKILL, SCRIPT, "--help")
    assert r.returncode == 0 and "accessibility" in r.stdout
