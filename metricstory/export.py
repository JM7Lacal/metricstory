"""Exportacion del informe. Markdown siempre; HTML imprimible para 'guardar como
PDF' desde el navegador sin dependencias pesadas.
"""

from __future__ import annotations

import html
import re
from datetime import date


def to_markdown(report_md: str, *, title: str = "Informe de campaña") -> str:
    stamp = date.today().isoformat()
    return f"# {title}\n\n_Generado el {stamp} · MetricStory_\n\n{report_md}\n"


def to_printable_html(report_md: str, *, title: str = "Informe de campaña") -> str:
    body = _markdown_to_html(report_md)
    stamp = date.today().isoformat()
    return f"""<!doctype html>
<html lang="es">
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
  body {{ font: 15px/1.6 -apple-system, Segoe UI, Roboto, sans-serif;
         max-width: 46rem; margin: 3rem auto; padding: 0 1.5rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.7rem; margin-bottom: 0.2rem; }}
  h2 {{ font-size: 1.2rem; margin-top: 2rem; border-bottom: 1px solid #ddd;
        padding-bottom: 0.3rem; }}
  .meta {{ color: #666; font-size: 0.85rem; margin-bottom: 2rem; }}
  ul {{ padding-left: 1.2rem; }}
  strong {{ color: #000; }}
  @media print {{ body {{ margin: 0; }} }}
</style>
<h1>{html.escape(title)}</h1>
<div class="meta">Generado el {stamp} · MetricStory</div>
{body}
</html>
"""


_INLINE_BOLD = re.compile(r"\*\*(.+?)\*\*")


def _markdown_to_html(md: str) -> str:
    """Conversor minimo: encabezados, listas, negrita y parrafos. Suficiente
    para el Markdown acotado que produce el informe."""
    lines = md.splitlines()
    out: list[str] = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for raw in lines:
        line = raw.rstrip()
        if not line:
            close_list()
            continue
        if line.startswith("### "):
            close_list()
            out.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            close_list()
            out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            close_list()
            out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.lstrip().startswith(("- ", "* ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(line.lstrip()[2:])}</li>")
        else:
            close_list()
            out.append(f"<p>{_inline(line)}</p>")

    close_list()
    return "\n".join(out)


def _inline(text: str) -> str:
    escaped = html.escape(text)
    return _INLINE_BOLD.sub(r"<strong>\1</strong>", escaped)
