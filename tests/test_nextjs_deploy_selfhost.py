import json

from conftest import FIXTURES, load_script, run_script

SKILL = "nextjs-deploy-selfhost"
SCRIPT = "selfhost_check.py"
mod = load_script(SKILL, SCRIPT)
F = FIXTURES / SKILL


def run_all(root, instances=1):
    has_docker = (root / "Dockerfile").is_file()
    return (
        mod.check_config(root, has_docker, instances)
        + mod.check_dockerfile(root)
        + mod.check_nginx(mod.find_nginx(root), root)
    )


def rules(findings):
    return {f["rule"] for f in findings}


def test_bad_project():
    r = rules(run_all(F / "bad", instances=2))
    assert {"DEP001", "DEP002", "DEP003", "DEP005", "DEP006", "DEP007"} <= r
    assert {"DEP021", "DEP022", "DEP027", "DEP028", "DEP029"} <= r
    assert {"DEP040", "DEP041", "DEP042", "DEP043", "DEP045", "DEP046"} <= r


def test_single_instance_skips_multi_instance_checks():
    r = rules(run_all(F / "bad", instances=1))
    assert not r & {"DEP005", "DEP006", "DEP007"}


def test_good_project_is_clean():
    assert run_all(F / "good", instances=3) == []


def test_export_mode():
    found = run_all(F / "export")
    files = {f["file"] for f in found if f["rule"] == "DEP010"}
    assert files == {"app/actions.ts", "app/api/contact/route.ts", "app/page.tsx", "proxy.ts"}
    assert "DEP011" in rules(found) and "DEP001" not in rules(found)


def write_standalone_dockerfile(tmp_path, body):
    (tmp_path / "Dockerfile").write_text("FROM node:22-alpine AS b\nFROM node:22-alpine\n" + body)
    (tmp_path / ".dockerignore").write_text("node_modules\n.next\n.git\n.env*\n")
    return rules(mod.check_dockerfile(tmp_path))


def test_standalone_without_static(tmp_path):
    r = write_standalone_dockerfile(
        tmp_path,
        "ENV NODE_ENV=production HOSTNAME=0.0.0.0\nCOPY --from=b /app/.next/standalone ./\nUSER node\n"
        'CMD ["npm", "start"]\n',
    )
    assert {"DEP023", "DEP024", "DEP026"} <= r and "DEP025" not in r


def test_node_versions(tmp_path):
    for image, flagged in (("node:20.8-alpine", "DEP021"), ("node:20.9-alpine", None), ("node:lts", "DEP020")):
        (tmp_path / "Dockerfile").write_text(f"FROM {image}\nUSER node\n")
        r = rules(mod.check_dockerfile(tmp_path))
        if flagged:
            assert flagged in r, image
        else:
            assert not r & {"DEP020", "DEP021"}, image


def test_dockerignore_missing_env(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM node:22\nUSER node\n")
    (tmp_path / ".dockerignore").write_text("node_modules\n")
    found = [f for f in mod.check_dockerfile(tmp_path) if f["rule"] == "DEP030"]
    assert {f["severity"] for f in found if ".env" in f["message"]} == {"high"}


def test_nginx_comments_ignored(tmp_path):
    conf = tmp_path / "x.conf"
    conf.write_text("location / {\n  proxy_pass http://app;\n  # proxy_set_header Host $host;\n}\n")
    assert "DEP040" in rules(mod.check_nginx([conf], tmp_path))


def test_cli():
    r = run_script(SKILL, SCRIPT, str(F / "bad"), "--json", "--instances", "2")
    assert r.returncode == 1 and json.loads(r.stdout)["summary"]["high"] >= 5
    assert run_script(SKILL, SCRIPT, str(F / "good"), "--instances", "2").returncode == 0
    nginx = F / "bad" / "nginx" / "site.conf"
    r = run_script(SKILL, SCRIPT, str(F / "good"), "--nginx", str(nginx))
    assert r.returncode == 1 and "DEP040" in r.stdout
    assert run_script(SKILL, SCRIPT, str(F / "good"), "--nginx", "missing.conf").returncode == 2
    assert run_script(SKILL, SCRIPT, str(F / "missing")).returncode == 2


def test_help():
    r = run_script(SKILL, SCRIPT, "--help")
    assert r.returncode == 0 and "--instances" in r.stdout
