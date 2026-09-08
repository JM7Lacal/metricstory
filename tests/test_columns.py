from metricstory.columns import guess_mapping


def test_guess_mapping_resolves_meta_ads_headers():
    headers = [
        "Reporting starts", "Campaign name", "Amount spent (USD)",
        "Impressions", "Link clicks", "Purchases", "Purchases conversion value",
    ]
    mapping = guess_mapping(headers)
    assert mapping.is_complete
    assert mapping.source_for("date") == "Reporting starts"
    assert mapping.source_for("spend") == "Amount spent (USD)"
    assert mapping.source_for("conversion_value") == "Purchases conversion value"


def test_guess_mapping_resolves_spanish_headers():
    headers = ["Fecha", "Nombre de la campaña", "Importe gastado (ARS)", "Impresiones", "Clics"]
    mapping = guess_mapping(headers)
    assert mapping.missing_required == []


def test_guess_mapping_flags_missing_required():
    mapping = guess_mapping(["Some Weird Column", "Another One"])
    assert not mapping.is_complete
    assert "spend" in mapping.missing_required
