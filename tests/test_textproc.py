import pytest

from create2tts.textproc import detect_language, normalize_text, split_segments


@pytest.mark.parametrize(
    "text,expected",
    [
        ("สวัสดีครับ", "th"),
        ("Hello world", "en"),
        ("ราคา iPhone 15 Pro", "th"),
        ("123", "th"),
    ],
)
def test_detect_language(text, expected):
    assert detect_language(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("ราคา 1,250 บาท", "ราคา หนึ่งพันสองร้อยห้าสิบ บาท"),
        ("3.5", "สามจุดห้า"),
        ("0.25", "ศูนย์จุดสองห้า"),
        ("ลด 20%", "ลด ยี่สิบเปอร์เซ็นต์"),
        ("฿100", "หนึ่งร้อยบาท"),
        ("ดีๆ", "ดีดี"),
    ],
)
def test_normalize_thai(text, expected):
    assert normalize_text(text, "th") == expected


def test_normalize_strips_markdown():
    out = normalize_text("**หัวข้อ** `x`", "th")
    assert "*" not in out and "`" not in out


def test_normalize_english_unchanged():
    assert normalize_text("It costs 5 dollars", "en") == "It costs 5 dollars"


def test_split_two_lines():
    assert len(split_segments("ฉันไปตลาดวันนี้\nเขาอยู่บ้านทั้งวัน", "th")) == 2


def test_split_merges_short_piece():
    items = split_segments("This is a long first sentence. ok.", "en")
    assert len(items) == 1
    assert items[0].endswith("ok.")


def test_split_long_thai_no_spaces():
    text = "สวัสดีครับวันนี้อากาศดีมาก" * 200
    assert len(text) >= 5000
    items = split_segments(text, "th")
    assert all(0 < len(i) <= 180 for i in items)
    assert "".join(items) == "".join(text.split())


def test_split_blank():
    assert split_segments("  ", "th") == []
