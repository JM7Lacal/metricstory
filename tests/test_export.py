from metricstory.export import _markdown_to_html, to_markdown, to_printable_html

SAMPLE = """\
## Resumen del periodo

La inversion fue de **USD 24.294**.

## Desempeño por campaña

- Black Friday: ROAS 3.88
- Branding: sin conversiones
"""


def test_markdown_to_html_renders_headings_lists_and_bold():
    html = _markdown_to_html(SAMPLE)
    assert "<h2>Resumen del periodo</h2>" in html
    assert "<strong>USD 24.294</strong>" in html
    assert html.count("<ul>") == 1 and html.count("</ul>") == 1
    assert "<li>Black Friday: ROAS 3.88</li>" in html


def test_markdown_to_html_escapes_raw_html():
    assert "&lt;script&gt;" in _markdown_to_html("un <script> suelto")


def test_to_printable_html_is_a_full_document_with_title():
    doc = to_printable_html(SAMPLE, title="Informe de prueba")
    assert doc.startswith("<!doctype html>")
    assert "<title>Informe de prueba</title>" in doc
    assert "@media print" in doc


def test_to_markdown_prepends_title_and_date_stamp():
    out = to_markdown("cuerpo", title="Informe X")
    assert out.startswith("# Informe X")
    assert "cuerpo" in out
