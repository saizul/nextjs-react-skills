import json

from conftest import FIXTURES, load_script, run_script

SKILL = "nextjs-seo-metadata"
SCRIPT = "seo_audit.py"
mod = load_script(SKILL, SCRIPT)
F = FIXTURES / SKILL


def rules(findings):
    return {f["rule"] for f in findings}


def test_bad_html():
    r = rules(mod.audit_html_dir(F / "html" / "bad"))
    assert {"SEO004", "SEO007", "SEO010", "SEO012", "SEO015", "SEO017", "SEO006", "SEO013"} <= r


def test_404_page_is_skipped():
    files = {f["file"] for f in mod.audit_html_dir(F / "html" / "bad")}
    assert "404.html" not in files


def test_good_html_is_clean():
    assert mod.audit_html_dir(F / "html" / "good") == []


def test_empty_dir(tmp_path):
    assert rules(mod.audit_html_dir(tmp_path)) == {"SEO000"}


def test_jsonld_variants():
    page = (
        '<html lang="en"><head><title>T</title>'
        '<script type="application/ld+json">{"@type": "Thing"}</script>'
        '<script type="application/ld+json">[{"@context": "https://schema.org"}]</script>'
        "</head><body><h1>x</h1></body></html>"
    )
    findings, _ = mod.audit_html_page(page, "p.html")
    msgs = [f["message"] for f in findings if f["rule"] == "SEO016"]
    assert any("@context" in m for m in msgs) and any("@type" in m for m in msgs)


def test_noindex_pages_skip_canonical_and_duplicates(tmp_path):
    for name in ("a.html", "b.html"):
        (tmp_path / name).write_text(
            '<html lang="en"><head><title>Same</title><meta name="robots" content="noindex"></head></html>'
        )
    r = rules(mod.audit_html_dir(tmp_path))
    assert "SEO017" not in r and "SEO006" not in r and "SEO008" in r


def test_bad_source():
    found = mod.audit_source(F / "source" / "bad")
    r = {(f["rule"], f["file"]) for f in found}
    assert ("SEO020", "app/pricing/page.tsx") in r
    assert ("SEO021", "app/blog/[slug]/page.tsx") in r
    assert ("SEO022", "app/page.tsx") in r
    assert ("SEO023", "app/faq/page.tsx") in r
    assert ("SEO024", "app/faq/page.tsx") in r
    assert ("SEO029", "app/robots.ts") in r
    assert {"SEO025", "SEO026", "SEO028", "SEO012"} <= rules(found)
    assert "SEO027" not in rules(found)  # robots.ts exists


def test_good_source_is_clean():
    assert mod.audit_source(F / "source" / "good") == []


def test_no_app_dir(tmp_path):
    assert rules(mod.audit_source(tmp_path)) == {"SEO000"}


def test_robots_txt_parsing():
    assert mod.blocks_everything((F / "robots" / "blocking.txt").read_text(), True)
    assert not mod.blocks_everything((F / "robots" / "googlebot-only.txt").read_text(), True)
    assert not mod.blocks_everything("User-agent: *\nDisallow:\n", True)


def test_robots_ts_parsing():
    assert mod.blocks_everything("rules: { userAgent: '*', disallow: ['/'] }", False)
    assert not mod.blocks_everything("rules: { userAgent: '*', disallow: '/admin' }", False)


def test_public_robots_txt_blocking(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "layout.tsx").write_text('export default function L({c}) { return <html lang="en">{c}</html> }')
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    assert "SEO029" in rules(mod.audit_source(tmp_path))


def test_cli():
    r = run_script(SKILL, SCRIPT, "html", str(F / "html" / "bad"), "--json")
    assert r.returncode == 1
    assert json.loads(r.stdout)["summary"]["high"] >= 2
    assert run_script(SKILL, SCRIPT, "source", str(F / "source" / "good")).returncode == 0
    assert run_script(SKILL, SCRIPT, "html", str(F / "missing")).returncode == 2
    low_only = run_script(SKILL, SCRIPT, "html", str(F / "html" / "bad"), "--fail-on", "high")
    assert low_only.returncode == 1


def test_help():
    r = run_script(SKILL, SCRIPT, "--help")
    assert r.returncode == 0 and "source" in r.stdout


def test_env_gated_robots_is_medium(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "robots.ts").write_text(
        "export default function robots() {\n  if (process.env.APP_ENV !== 'production') "
        "return { rules: { userAgent: '*', disallow: '/' } }\n  return { rules: { userAgent: '*', allow: '/' } }\n}\n"
    )
    sev = [f["severity"] for f in mod.audit_source(tmp_path) if f["rule"] == "SEO029"]
    assert sev == ["medium"]
