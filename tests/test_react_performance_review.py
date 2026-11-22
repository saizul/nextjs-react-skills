import json
import os

from conftest import FIXTURES, load_script, run_script

SKILL = "react-performance-review"
SCRIPT = "bundle_report.py"
mod = load_script(SKILL, SCRIPT)
F = FIXTURES / SKILL


def test_parse_build_log_15():
    parsed = mod.parse_build_log((F / "build-log-15.txt").read_text())
    routes = {r["route"]: r for r in parsed["routes"]}
    assert set(routes) == {"/", "/_not-found", "/api/search", "/blog/[slug]", "/dashboard", "/editor"}
    assert routes["/editor"]["first_load_kb"] == 1200
    assert routes["/_not-found"]["size_kb"] == 0.99
    assert routes["/blog/[slug]"]["type"] == "●"
    assert parsed["shared_kb"] == 102


def test_build_log_16_has_no_sizes():
    assert mod.parse_build_log((F / "build-log-16.txt").read_text())["routes"] == []


def test_route_budgets():
    parsed = mod.parse_build_log((F / "build-log-15.txt").read_text())
    found = mod.check_routes(parsed["routes"], parsed["shared_kb"], 170, 300, "log")
    sev = {f["message"].split()[1]: f["severity"] for f in found}
    assert sev == {"/editor": "high", "/dashboard": "medium"}
    tight = mod.check_routes(parsed["routes"], parsed["shared_kb"], 100, 300, "log")
    assert any(f["rule"] == "PERF002" for f in tight)


def test_stats_heavy_and_duplicate_packages():
    data = json.loads((F / "stats.json").read_text())
    found, info = mod.analyze_stats(data, 100, "stats.json")
    msgs = " ".join(f["message"] for f in found)
    assert "chart.js" in msgs and "moment" in msgs and "lodash" in msgs
    assert any(f["rule"] == "PERF005" and "lodash" in f["message"] for f in found)
    assert any(f["rule"] == "PERF003" for f in found)
    assert not any("app.css" in f["message"] for f in found)
    assert info["top_packages_kb"]["chart.js"] == 200


def test_stats_children_format():
    data = {"children": [json.loads((F / "stats.json").read_text())]}
    found, _ = mod.analyze_stats(data, 100, "s")
    assert any(f["rule"] == "PERF004" for f in found)


def test_clean_stats():
    found, _ = mod.analyze_stats(json.loads((F / "stats-clean.json").read_text()), 100, "s")
    assert found == []


def test_package_of():
    assert mod.package_of("./node_modules/@mui/icons-material/esm/Delete.js") == "@mui/icons-material"
    assert mod.package_of("./node_modules/a/node_modules/lodash/x.js") == "lodash"
    assert mod.package_of("./src/app.ts") is None


def make_next_dir(tmp_path, big_kb=150):
    nd = tmp_path / ".next"
    chunks = nd / "static" / "chunks"
    (chunks / "app" / "editor").mkdir(parents=True)
    (chunks / "main-app.js").write_bytes(b"console.log('main');" * 200)
    (chunks / "app" / "editor" / "page.js").write_bytes(os.urandom(big_kb * 1000))
    (chunks / "app" / "page.js").write_bytes(b"export default 1;" * 100)
    manifest = {
        "pages": {
            "/editor/page": ["static/chunks/app/editor/page.js"],
            "/page": ["static/chunks/app/page.js"],
        },
        "rootMainFiles": ["static/chunks/main-app.js"],
    }
    (nd / "app-build-manifest.json").write_text(json.dumps(manifest))
    return nd


def test_next_dir(tmp_path):
    nd = make_next_dir(tmp_path)
    found, info = mod.analyze_next_dir(nd, 120, 300, 100)
    routes = {r["route"]: r["first_load_kb"] for r in info["routes"]}
    assert routes["/editor/page"] > 140 and routes["/page"] < 5
    rules = {(f["rule"], f["file"]) for f in found}
    assert ("PERF006", "static/chunks/app/editor/page.js") in rules
    assert ("PERF001", "/editor/page") in rules
    assert info["chunks"] == 3


def test_next_dir_without_static(tmp_path):
    found, _ = mod.analyze_next_dir(tmp_path, 170, 300, 100)
    assert found[0]["rule"] == "PERF000"


def test_cli(tmp_path):
    r = run_script(SKILL, SCRIPT, "--build-log", str(F / "build-log-15.txt"))
    assert r.returncode == 1 and "/editor" in r.stdout
    r = run_script(SKILL, SCRIPT, "--build-log", str(F / "build-log-16.txt"))
    assert r.returncode == 2 and "--next-dir" in r.stderr
    r = run_script(SKILL, SCRIPT, "--stats", str(F / "stats-clean.json"), "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["findings"] == []
    nd = make_next_dir(tmp_path)
    r = run_script(SKILL, SCRIPT, "--next-dir", str(nd), "--json")
    assert r.returncode == 1 and json.loads(r.stdout)["data"]["next_dir"]["chunks"] == 3
    assert run_script(SKILL, SCRIPT).returncode == 2
    assert run_script(SKILL, SCRIPT, "--stats", str(tmp_path / "none.json")).returncode == 2


def test_help():
    r = run_script(SKILL, SCRIPT, "--help")
    assert r.returncode == 0 and "--next-dir" in r.stdout
