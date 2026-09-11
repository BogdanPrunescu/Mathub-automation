from mathub_extractor.poppler import _escape_xml_illegal_controls, _restore_word


def test_illegal_xml_controls_are_preserved_as_unresolved() -> None:
    safe, count = _escape_xml_illegal_controls("x\x1dy")
    assert count == 1
    restored, codes = _restore_word(safe)
    assert restored == "x\ufffdy"
    assert codes == ["U+001D"]
