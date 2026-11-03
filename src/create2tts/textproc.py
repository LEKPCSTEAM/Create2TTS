import re

from pythainlp.tokenize import sent_tokenize, word_tokenize
from pythainlp.util import num_to_thaiword

from create2tts.models import Language

_THAI_RE = re.compile(r"[฀-๿]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_NUM = r"\d+(?:,\d{3})*(?:\.\d+)?"
_BAHT_RE = re.compile(rf"฿\s*({_NUM})")
_PERCENT_RE = re.compile(rf"({_NUM})\s*%")
_NUM_RE = re.compile(_NUM)
_MARKDOWN_LINE_RE = re.compile(r"^\s*[#>]+\s*")
_MIN_PIECE = 8


def detect_language(text: str) -> Language:
    thai = len(_THAI_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    if thai + latin == 0:
        return "th"
    return "th" if thai / (thai + latin) >= 0.2 else "en"


def _number_to_words(raw: str) -> str:
    whole, _, frac = raw.replace(",", "").partition(".")
    words = num_to_thaiword(int(whole))
    if frac:
        words += "จุด" + "".join(num_to_thaiword(int(d)) for d in frac)
    return words


def _expand_repeat_marks(text: str) -> str:
    while (idx := text.find("ๆ")) != -1:
        before = text[:idx]
        tokens = word_tokenize(before[-40:], keep_whitespace=False)
        text = before + (tokens[-1] if tokens else "") + text[idx + 1 :]
    return text


def normalize_text(text: str, language: Language) -> str:
    lines = []
    for line in text.splitlines():
        line = _MARKDOWN_LINE_RE.sub("", line).replace("*", "").replace("`", "")
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)
    out = "\n".join(lines)
    if language != "th":
        return out
    out = _BAHT_RE.sub(lambda m: _number_to_words(m.group(1)) + "บาท", out)
    out = _PERCENT_RE.sub(lambda m: _number_to_words(m.group(1)) + "เปอร์เซ็นต์", out)
    out = _NUM_RE.sub(lambda m: _number_to_words(m.group(0)), out)
    return _expand_repeat_marks(out)


def _sentences(line: str, language: Language) -> list[str]:
    if language == "th":
        return [s.strip() for s in sent_tokenize(line, engine="crfcut") if s.strip()]
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()]


def _merge_short(pieces: list[str]) -> list[str]:
    merged: list[str] = []
    carry = ""
    for piece in pieces:
        if carry:
            piece = f"{carry} {piece}"
            carry = ""
        if len(piece) < _MIN_PIECE:
            if merged:
                merged[-1] = f"{merged[-1]} {piece}"
            else:
                carry = piece
        else:
            merged.append(piece)
    if carry:
        merged.append(carry)
    return merged


def _split_long(piece: str, language: Language, max_chars: int) -> list[str]:
    if len(piece) <= max_chars:
        return [piece]
    if language == "th":
        tokens = word_tokenize(piece)
    else:
        tokens = re.findall(r"\S+\s*", piece)
    chunks: list[str] = []
    current = ""
    for token in tokens:
        while len(token) > max_chars:
            room = max_chars - len(current)
            if room <= 0:
                chunks.append(current)
                current = ""
                continue
            current += token[:room]
            token = token[room:]
        if len(current) + len(token) > max_chars:
            chunks.append(current)
            current = ""
        current += token
    chunks.append(current)
    return [c.strip() for c in chunks if c.strip()]


def _pack(pieces: list[str], max_chars: int) -> list[str]:
    packed: list[str] = []
    for piece in pieces:
        if packed and len(packed[-1]) + 1 + len(piece) <= max_chars:
            packed[-1] = f"{packed[-1]} {piece}"
        else:
            packed.append(piece)
    return packed


def split_segments(text: str, language: Language, max_chars: int = 180) -> list[str]:
    result: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        pieces: list[str] = []
        for piece in _merge_short(_sentences(line, language)):
            pieces.extend(_split_long(piece, language, max_chars))
        result.extend(_pack(pieces, max_chars))
    return result
