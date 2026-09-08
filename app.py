"""MetricStory — UI de Streamlit.

Flujo: subir CSV -> mapear columnas -> ver metricas -> elegir tono ->
generar informe -> exportar -> conversar sobre el informe.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import streamlit as st

from metricstory import service
from metricstory.columns import CANONICAL_FIELDS, REQUIRED_FIELDS, ColumnMapping, guess_mapping
from metricstory.config import AppConfig
from metricstory.export import to_markdown, to_printable_html
from metricstory.facts import ReportFacts
from metricstory.llm import ChatModelError, available_providers
from metricstory.metrics import build_facts
from metricstory.report import QA, TONES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

SAMPLE_PATH = Path(__file__).parent / "samples" / "meta-ads-sample.csv"

st.set_page_config(page_title="MetricStory", page_icon="📊", layout="wide")

st.markdown(
    """
    <style>
      /* scrollbars mas anchos que los finos de Streamlit */
      ::-webkit-scrollbar { width: 14px; height: 14px; }
      ::-webkit-scrollbar-track { background: transparent; }
      ::-webkit-scrollbar-thumb {
        background: #b8c2ce; border-radius: 7px;
        border: 3px solid transparent; background-clip: content-box;
      }
      ::-webkit-scrollbar-thumb:hover { background: #97a3b2; background-clip: content-box; }

      /* reservar siempre el gutter: el contenido no se corre cuando la barra
         aparece o desaparece */
      [data-testid="stMain"], [data-testid="stAppViewContainer"],
      section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div {
        scrollbar-gutter: stable;
      }

      /* menos aire arriba del contenido principal */
      .block-container { padding-top: 2.2rem; padding-bottom: 2rem; }

      /* file uploader compacto: solo el boton, sin el bloque de instrucciones */
      section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
        padding: 0.5rem 0.75rem;
      }
      section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] {
        display: none;
      }

      /* sidebar compacto: sacar el espacio muerto del encabezado y juntar controles */
      section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {
        padding-top: 0.4rem; padding-bottom: 0.2rem; min-height: 0;
      }
      section[data-testid="stSidebar"] [data-testid="stLogoSpacer"] { display: none; }
      section[data-testid="stSidebar"] .block-container { padding-top: 0.5rem; }
      section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.5rem; }
      section[data-testid="stSidebar"] h2 { font-size: 1.05rem; margin: 0.4rem 0 0; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def _config() -> AppConfig:
    return AppConfig.load()


def _fmt_money(v, currency: str) -> str:
    return f"{currency} {v:,.0f}" if isinstance(v, (int, float)) else "—"


def _fmt_pct(v) -> str:
    return f"{v * 100:+.1f}%" if isinstance(v, (int, float)) else "s/d"


def _fmt_ratio(v) -> str:
    return f"{v:.2f}" if isinstance(v, (int, float)) else "s/d"


def main() -> None:
    cfg = _config()
    st.title("📊 MetricStory")
    st.caption("De las métricas de campaña al informe que le mandás al cliente.")

    with st.sidebar:
        st.header("Datos")
        if st.session_state.get("use_sample"):
            st.caption("📄 Usando datos de ejemplo (Meta Ads)")
            if st.button("Subir otro archivo"):
                st.session_state["use_sample"] = False
                st.rerun()
            uploaded = None
        else:
            st.caption("Subí el export de tu plataforma de ads (CSV)")
            uploaded = st.file_uploader(
                "CSV de la plataforma de ads", type=["csv"], label_visibility="collapsed"
            )
            if uploaded is None and st.button("📎 Usar datos de ejemplo (Meta Ads)"):
                st.session_state["use_sample"] = True
                st.rerun()
        use_sample = st.session_state.get("use_sample", False) and uploaded is None

        if uploaded is not None or use_sample:
            st.header("Cuenta")
            c1, c2 = st.columns([1, 1.6])
            currency = c1.text_input("Moneda", value=cfg.account_currency)
            budget = c2.number_input(
                "Presupuesto/mes", min_value=0.0, value=float(cfg.monthly_budget or 0),
                step=500.0, help="0 = no mostrar el ritmo de gasto",
            )

            st.header("Informe")
            tone = st.selectbox(
                "Audiencia / tono", options=list(TONES), index=list(TONES).index(cfg.default_tone),
                format_func=lambda k: {"cliente": "Cliente (no técnico)",
                                        "interno": "Equipo interno",
                                        "ejecutivo": "Dirección / ejecutivo"}[k],
            )
            provider = st.selectbox(
                "Proveedor de IA", options=available_providers(),
                index=available_providers().index(cfg.provider) if cfg.provider in available_providers() else 0,
            )
        else:
            currency = cfg.account_currency
            budget = float(cfg.monthly_budget or 0)
            tone = cfg.default_tone
            provider = cfg.provider

    raw_df, source_label = _load_source(uploaded, use_sample)
    if raw_df is None:
        for k in ("report_md", "report_md_prev", "report_provider", "report_source_key", "conversation"):
            st.session_state.pop(k, None)
        st.info("Subí un CSV o probá con el ejemplo en la barra lateral para arrancar.")
        return

    source_key = f"{source_label}|{len(raw_df)}"
    if st.session_state.get("report_source_key") != source_key:
        for k in ("report_md", "report_md_prev", "report_provider", "conversation"):
            st.session_state.pop(k, None)
    st.session_state["report_source_key"] = source_key

    mapping = guess_mapping(list(raw_df.columns))
    mapping = _mapping_editor(raw_df, mapping)

    if not mapping.is_complete:
        st.error(
            "Faltan mapear columnas obligatorias: "
            + ", ".join(mapping.missing_required)
        )
        return

    try:
        facts = build_facts(
            raw_df, mapping,
            account_currency=currency or "USD",
            monthly_budget=budget or None,
        )
    except ValueError as exc:
        st.error(f"No se pudo procesar el CSV: {exc}")
        return

    tab_data, tab_report, tab_chat = st.tabs(
        ["📈 Datos y métricas", "📝 Informe", "💬 Conversación"]
    )

    with tab_data:
        st.caption(f"Fuente: {source_label} · {len(raw_df)} filas · {len(facts.campaigns)} campañas")
        _render_facts(facts)

    with tab_report:
        _render_report_tab(facts, cfg, tone=tone, provider=provider)

    with tab_chat:
        _render_chat_tab(facts, cfg, tone=tone, provider=provider)


def _render_report_tab(facts: ReportFacts, cfg: AppConfig, *, tone: str, provider: str) -> None:
    st.caption(
        "Redactado a partir de las métricas de la pestaña anterior. "
        "Revisá el informe antes de enviarlo al cliente."
    )

    if st.button("✍️ Generar informe", type="primary"):
        with st.spinner(f"Redactando con el proveedor «{provider}»…"):
            try:
                report = service.generate(facts, cfg, tone=tone, provider=provider)
                st.session_state["report_md"] = report.markdown
                st.session_state["report_provider"] = report.provider
                st.session_state["conversation"] = []
                st.session_state.pop("report_md_prev", None)
            except ChatModelError as exc:
                st.error(f"El proveedor «{provider}» no pudo responder: {exc}")

    if "report_md" not in st.session_state:
        return

    with st.container(border=True):
        st.markdown(_escape_for_streamlit_markdown(st.session_state["report_md"]))
    st.caption(f"Generado con: {st.session_state.get('report_provider', provider)}")

    col1, col2 = st.columns(2)
    col1.download_button(
        "⬇️ Descargar Markdown",
        data=to_markdown(st.session_state["report_md"]),
        file_name="informe-campana.md",
        mime="text/markdown",
    )
    col2.download_button(
        "⬇️ Versión imprimible (HTML)",
        data=to_printable_html(st.session_state["report_md"]),
        file_name="informe-campana.html",
        mime="text/html",
        help="Abrila en el navegador y usá Imprimir → Guardar como PDF.",
    )

    if "report_md_prev" in st.session_state:
        if st.button("↩︎ Deshacer último cambio"):
            st.session_state["report_md"] = st.session_state.pop("report_md_prev")
            st.toast("Cambio deshecho", icon="↩️")
            st.rerun()

    with st.form("edit_report", clear_on_submit=True):
        edit_req = st.text_input(
            "✏️ Pedí un cambio",
            placeholder='Ej: "hacé el resumen más corto" o "sumá una recomendación sobre Branding"',
        )
        submitted = st.form_submit_button("Aplicar cambio")
    if submitted and edit_req:
        try:
            with st.spinner("Aplicando el cambio…"):
                new_md = service.apply_edit(
                    facts, cfg,
                    current_report=st.session_state["report_md"],
                    request=edit_req,
                    tone=tone,
                    provider=provider,
                )
            st.session_state["report_md_prev"] = st.session_state["report_md"]
            st.session_state["report_md"] = new_md
            st.toast("Informe actualizado", icon="✅")
            st.rerun()
        except ChatModelError as exc:
            st.error(f"No se pudo aplicar el cambio: {exc}")


def _render_chat_tab(facts: ReportFacts, cfg: AppConfig, *, tone: str, provider: str) -> None:
    if "report_md" not in st.session_state:
        st.info("Generá el informe en la pestaña «Informe» antes de conversar sobre él.")
        return

    st.caption(
        "Preguntá sobre los números del período. Las respuestas no modifican el informe."
    )

    st.session_state.setdefault("conversation", [])
    with st.container(border=True, height=380):
        if not st.session_state["conversation"]:
            st.caption("Sin preguntas todavía — escribí una abajo.")
        for turn in st.session_state["conversation"]:
            with st.chat_message("user" if turn["role"] == "user" else "assistant"):
                st.markdown(_escape_for_streamlit_markdown(turn["content"]))

    with st.form("ask_question", clear_on_submit=True):
        question = st.text_input(
            "❓ Tu pregunta",
            placeholder='Ej: "por qué cayó el ROAS de Prospecting - Intereses amplios?"',
        )
        asked = st.form_submit_button("Preguntar")
    if asked and question:
        history = _qa_history(st.session_state["conversation"])
        st.session_state["conversation"].append({"role": "user", "content": question})
        try:
            with st.spinner("Pensando…"):
                reply = service.ask(
                    facts, cfg,
                    current_report=st.session_state["report_md"],
                    question=question,
                    history=history,
                    tone=tone,
                    provider=provider,
                )
            st.session_state["conversation"].append({"role": "assistant", "content": reply})
        except ChatModelError as exc:
            st.session_state["conversation"].append(
                {"role": "assistant", "content": f"⚠️ No pude responder: {exc}"}
            )
        st.rerun()


def _qa_history(conversation: list[dict]) -> list[QA]:
    """Empareja los turnos user→assistant ya cerrados en objetos QA."""
    out: list[QA] = []
    pending_q: str | None = None
    for turn in conversation:
        if turn["role"] == "user":
            pending_q = turn["content"]
        elif turn["role"] == "assistant" and pending_q is not None:
            out.append(QA(question=pending_q, answer=turn["content"]))
            pending_q = None
    return out


def _load_source(uploaded, use_sample: bool) -> tuple[pd.DataFrame | None, str]:
    if uploaded is not None:
        return pd.read_csv(uploaded), uploaded.name
    if use_sample:
        return pd.read_csv(SAMPLE_PATH), "samples/meta-ads-sample.csv"
    return None, ""


def _escape_for_streamlit_markdown(text: str) -> str:
    """`st.markdown` interpreta `$..$` como LaTeX (KaTeX): un informe con
    importes en dolares ("$24,293.86") sale mostrado como una formula rota.
    El informe nunca necesita LaTeX, asi que se escapa el signo pesos antes de
    mostrarlo en pantalla. Los archivos exportados usan el texto sin escapar.
    """
    return text.replace("$", "\\$")


def _mapping_editor(df: pd.DataFrame, mapping: ColumnMapping) -> ColumnMapping:
    """Deja revisar/corregir el mapeo automatico. Colapsado si no falta nada."""
    ok = mapping.is_complete
    with st.expander("Mapeo de columnas" + (" ✅" if ok else " ⚠️ falta completar"), expanded=not ok):
        cols = ["(ninguna)"] + list(df.columns)
        new_mapping: dict[str, str] = {}
        c1, c2 = st.columns(2)
        for i, field in enumerate(CANONICAL_FIELDS):
            target = c1 if i % 2 == 0 else c2
            current = mapping.source_for(field)
            idx = cols.index(current) if current in cols else 0
            label = field + (" *" if field in REQUIRED_FIELDS else "")
            picked = target.selectbox(label, cols, index=idx, key=f"map_{field}")
            if picked != "(ninguna)":
                new_mapping[field] = picked
        st.caption("* obligatorio")
    return ColumnMapping(mapping=new_mapping)


def _render_facts(facts: ReportFacts) -> None:
    cur, prev, deltas = facts.total_current, facts.total_previous, facts.total_deltas
    c = facts.account_currency

    with st.container(border=True):
        st.markdown(
            f"**Período actual:** {facts.current_period[0]} a {facts.current_period[1]}"
            + (f" · **Período anterior:** {facts.previous_period[0]} a {facts.previous_period[1]}"
               if facts.previous_period else "")
        )

        cols = st.columns(5)
        cols[0].metric("Inversión", _fmt_money(cur.spend, c), _fmt_pct(deltas.get("spend")))
        cols[1].metric("Clicks", f"{cur.clicks:,}", _fmt_pct(deltas.get("clicks")))
        cols[2].metric("CTR", f"{cur.ctr*100:.2f}%" if cur.ctr is not None else "—",
                        _fmt_pct(deltas.get("ctr")))
        cols[3].metric("CPA", _fmt_money(cur.cpa, c) if cur.cpa is not None else "—",
                        _fmt_pct(deltas.get("cpa")), delta_color="inverse")
        cols[4].metric("ROAS", _fmt_ratio(cur.roas), _fmt_pct(deltas.get("roas")))

        if facts.budget:
            b = facts.budget
            period_closed = b.days_elapsed >= b.days_in_period
            label = (
                f"Ritmo de gasto: {_fmt_money(b.spent, c)} de {_fmt_money(b.monthly_budget, c)} "
                f"({b.spent_pct*100:.0f}%)"
            )
            if not period_closed:
                label += f" · proyectado a fin de período: {_fmt_money(b.projected_spend, c)}"
            st.progress(min(b.spent_pct, 1.0), text=label)
            if b.spent_pct > 1.0:
                st.warning(
                    f"Sobregasto: {_fmt_money(b.spent - b.monthly_budget, c)} por encima "
                    "del presupuesto.",
                    icon="⚠️",
                )
            elif not period_closed and b.projected_spend > b.monthly_budget:
                st.warning(
                    f"Proyección por encima del presupuesto: {_fmt_money(b.projected_spend, c)} "
                    f"vs. {_fmt_money(b.monthly_budget, c)}.",
                    icon="⚠️",
                )

    with st.container(border=True):
        st.markdown("**Por campaña**")
        rows = []
        for camp in facts.campaigns:
            rows.append({
                "Campaña": camp.name,
                "Inversión": camp.current.spend,
                "% del total": camp.spend_share,
                "CTR": camp.current.ctr,
                "CPA": camp.current.cpa,
                "ROAS": camp.current.roas,
                "Δ ROAS": camp.deltas.get("roas"),
            })
        table = pd.DataFrame(rows)
        st.dataframe(
            table,
            column_config={
                "Inversión": st.column_config.NumberColumn(format=f"{c} %.0f"),
                "% del total": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=1),
                "CTR": st.column_config.NumberColumn(format="%.2f%%"),
                "CPA": st.column_config.NumberColumn(format=f"{c} %.1f"),
                "ROAS": st.column_config.NumberColumn(format="%.2fx"),
                "Δ ROAS": st.column_config.NumberColumn(format="%+.1f%%"),
            },
            hide_index=True,
            use_container_width=True,
        )

        if facts.notes:
            for note in facts.notes:
                st.caption(f"ℹ️ {note}")

        chart_df = pd.DataFrame([
            {"Campaña": r["Campaña"], "Inversión": r["Inversión"]} for r in rows
        ])
        st.bar_chart(chart_df, x="Campaña", y="Inversión", horizontal=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        # Deja pasar el control de flujo interno de Streamlit (st.rerun / st.stop).
        if type(exc).__name__ in {"RerunException", "StopException"}:
            raise
        st.error(
            "Algo se rompió procesando esto. Revisá que el CSV tenga columnas de "
            f"métricas reconocibles y volvé a intentar.\n\nDetalle: `{exc}`"
        )
