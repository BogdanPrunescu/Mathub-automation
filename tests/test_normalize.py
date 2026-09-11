from mathub_extractor.normalize import normalize_poppler_text


def test_legacy_romanian_normalization() -> None:
    original = "Legi de compoziþie. Sã facem cunoºtinþã."
    assert normalize_poppler_text(original) == (
        "Legi de compoziţie. Să facem cunoştinţă."
    )


def test_cp1252_control_repair() -> None:
    assert normalize_poppler_text("2 \x96 5") == "2 – 5"
