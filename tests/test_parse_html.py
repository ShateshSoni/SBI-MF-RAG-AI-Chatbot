"""HTML parser keeps form copy, drops controls, and flags JS shells."""

from __future__ import annotations

from pathlib import Path

from src.ingest.manifest import Doc
from src.ingest.parse_html import parse_html


def _doc() -> Doc:
    return Doc(
        doc_id="sample",
        title="Sample",
        doc_type="campaign",
        scheme="SBI Long Term Equity Fund",
        scheme_category="ELSS",
        source_url="https://www.sbimf.com/campaign/sbi-long-term-equity-fund",
        as_of_date="2026-01-01",
        tier=2,
        ingest=True,
        local_filename="",
        fetched_at="",
        notes="",
    )


def test_keeps_form_copy_and_lists(tmp_path: Path) -> None:
    html = """
    <html><body>
    <nav>Ignore this navigation</nav>
    <form>
      <p>SBI Long Term Equity Fund has a lock-in period of 3 years.</p>
      <label>PAN</label><input value="ABCDE1234F">
      <button>Submit</button>
      <ul><li>Open the statement portal.</li><li>Download the capital-gains statement.</li></ul>
    </form>
    </body></html>
    """
    path = tmp_path / "page.html"
    path.write_text(html, encoding="utf-8")
    blocks, meta = parse_html(path, _doc())
    text = "\n".join(block.text for block in blocks)
    assert "lock-in period of 3 years" in text
    assert "Open the statement portal." in text
    assert "Download the capital-gains statement." in text
    assert "Ignore this navigation" not in text
    assert "ABCDE1234F" not in text
    assert "Submit" not in text
    assert any(block.kind == "list_item" for block in blocks)
    assert meta.flag == ""


def test_flags_js_placeholder(tmp_path: Path) -> None:
    html = "<html><body><table><tr><td>Loading...</td></tr></table><p>No Records Found</p></body></html>"
    path = tmp_path / "thin.html"
    path.write_text(html, encoding="utf-8")
    _blocks, meta = parse_html(path, _doc())
    assert meta.flag == "POSSIBLY_JS_RENDERED"
