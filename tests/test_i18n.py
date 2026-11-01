"""الترجمة: كل نص عربي في الواجهة له ترجمة إنجليزية بنفس المتغيرات."""

import ast
import re
import string
from pathlib import Path

import pytest

from lockcontrol import i18n
from lockcontrol.en import EN

SRC = Path(__file__).resolve().parents[1] / "src" / "lockcontrol"
ARABIC = re.compile(r"[؀-ۿ]")
SKIP = {"cli.py", "en.py", "i18n.py"}  # أداة المطوّر تبقى عربية


def _docstrings(tree):
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def source_texts():
    """(النصوص العربية الثابتة، f-strings عربية متبقية)"""
    texts, fstrings = {}, []
    for path in SRC.rglob("*.py"):
        if path.name in SKIP:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs = _docstrings(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr) and ARABIC.search(ast.unparse(node)):
                fstrings.append(f"{path.name}:{node.lineno}")
            elif (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docs
                and ARABIC.search(node.value)
            ):
                texts[node.value] = f"{path.name}:{node.lineno}"
    return texts, fstrings


def fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_no_untranslatable_fstrings():
    _, fstrings = source_texts()
    assert fstrings == [], "حوّل هذه إلى t(\"...{x}...\", x=...): " + ", ".join(fstrings)


def test_every_arabic_text_has_english():
    texts, _ = source_texts()
    missing = [f"{where}: {text}" for text, where in texts.items() if text not in EN]
    assert missing == [], "ترجمات ناقصة:\n" + "\n".join(missing)


def test_translations_keep_placeholders():
    for ar, en in EN.items():
        assert fields(ar) == fields(en), f"{ar!r} → {en!r}"
        assert not ARABIC.search(en), en


def test_no_unused_translations():
    texts, _ = source_texts()
    assert sorted(set(EN) - set(texts)) == []


@pytest.fixture
def english():
    i18n.set_language("en")
    yield
    i18n.set_language("ar")


def test_t_formats_in_both_languages(english):
    assert i18n.t("تم فتح {name}".replace("تم فتح", "✓ تم فتح"), name="Door") == "✓ Unlocked Door"
    i18n.set_language("ar")
    assert i18n.t("✓ تم فتح {name}", name="الباب") == "✓ تم فتح الباب"
    assert i18n.is_rtl()


def test_unknown_language_falls_back_to_arabic():
    i18n.set_language("xx")
    assert i18n.language() == "ar"
