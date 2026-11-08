from app.domain.shared.names import name_variants


def test_variants_cover_name_order_and_initials():
    assert name_variants("Monkey D. Luffy") == ["Monkey D. Luffy", "Luffy D. Monkey", "Monkey Luffy", "Luffy Monkey"]
    assert name_variants("Gojo Satoru") == ["Gojo Satoru", "Satoru Gojo"]
    assert name_variants("Luffy") == ["Luffy"]
    assert name_variants("") == []
