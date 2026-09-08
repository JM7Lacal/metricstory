from __future__ import annotations

import json

from .base import ChatMessage, ChatModel


class StubChatModel(ChatModel):
    """Proveedor sin red. Arma un informe plausible a partir del JSON de hechos
    que viene en el mensaje del usuario.

    Sirve para: correr el demo sin internet ni API key, y para los tests (salida
    deterministica). No pretende escribir bien: pretende no romper.
    """

    name = "stub"

    def complete(self, messages: list[ChatMessage], *, temperature: float = 0.4) -> str:
        # El JSON de hechos vive en el user prompt para un informe nuevo, pero
        # en el system prompt para una conversacion de seguimiento (converse) -
        # se busca en todos los mensajes, del mas reciente al mas viejo.
        payload = None
        for msg in reversed(messages):
            payload = _extract_json(msg.content)
            if payload:
                break
        if not payload:
            return "## Informe de campaña\n\n_(stub sin datos)_"

        cur = payload.get("total_current", {})
        deltas = payload.get("total_deltas", {})
        cur_period = payload.get("current_period", ["", ""])
        currency = payload.get("account_currency", "")

        def money(v):
            return f"{currency} {v:,.0f}" if isinstance(v, (int, float)) else "-"

        def pct(v):
            return f"{v * 100:+.1f}%" if isinstance(v, (int, float)) else "s/d"

        lines = [
            f"## Informe de campaña · {cur_period[0]} a {cur_period[1]}",
            "",
            "### Resumen",
            f"- Inversion del periodo: **{money(cur.get('spend'))}** "
            f"({pct(deltas.get('spend'))} vs. periodo anterior).",
            f"- ROAS: **{cur.get('roas'):.2f}**" if isinstance(cur.get("roas"), (int, float))
            else "- ROAS: s/d",
            f"- CPA: **{money(cur.get('cpa'))}** ({pct(deltas.get('cpa'))}).",
            "",
            "### Por campaña",
        ]
        for c in payload.get("campaigns", [])[:6]:
            cb = c.get("current", {})
            roas = cb.get("roas")
            roas_txt = f"ROAS {roas:.2f}" if isinstance(roas, (int, float)) else "sin valor de conv."
            lines.append(
                f"- **{c.get('name')}**: {money(cb.get('spend'))} de inversion, {roas_txt}."
            )

        notes = payload.get("notes") or []
        if notes:
            lines += ["", "### Notas", *[f"- {n}" for n in notes]]

        lines += [
            "",
            "### Recomendaciones",
            "- Reasignar presupuesto hacia las campañas con mejor ROAS.",
            "- Revisar creatividades en las campañas con CPA en alza.",
            "",
            "_Borrador generado por el proveedor stub (sin IA). "
            "Configura un proveedor real en config.toml para el texto final._",
        ]
        return "\n".join(lines)


def _extract_json(text: str) -> dict | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
