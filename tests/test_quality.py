from mathub_extractor.quality import assess_text


def test_control_heavy_text_is_unusable() -> None:
    result = assess_text("\x02\x03\x04\x05abc")
    assert result.status == "UNUSABLE"


def test_clean_text_is_good() -> None:
    result = assess_text("Legi de compoziţie. Mulţimea numerelor reale.")
    assert result.status == "GOOD"
