from PIL import Image, ImageDraw

from app.services import composite


def _draw():
    img = Image.new("RGB", (900, 1200))
    return ImageDraw.Draw(img)


def test_wrap_text_short_single_line():
    draw = _draw()
    font = composite._load_font(30)
    lines = composite.wrap_text(draw, "短文本", font, 500)
    assert lines == ["短文本"]


def test_wrap_text_long_wraps():
    draw = _draw()
    font = composite._load_font(40)
    text = "这是一段很长的中文文本需要被折成多行显示"
    lines = composite.wrap_text(draw, text, font, 200)
    assert len(lines) > 1
    # 每行宽度都不超过 max_width
    for line in lines:
        w, _ = composite._text_size(draw, line, font)
        assert w <= 200


def test_wrap_text_empty():
    draw = _draw()
    assert composite.wrap_text(draw, "", composite._load_font(30), 100) == [""]


def test_fit_font_keeps_within_max_lines():
    draw = _draw()
    text = "十四个字的标题" * 5  # 很长
    font, lines, size, truncated = composite.fit_font(draw, text, 300, 2, start_size=72)
    assert len(lines) <= 2
    assert size >= 16
    assert isinstance(truncated, bool)
    for line in lines:
        w, _ = composite._text_size(draw, line, font)
        assert w <= 300


def test_fit_font_extreme_truncates():
    draw = _draw()
    text = "字" * 200
    font, lines, size, truncated = composite.fit_font(
        draw, text, 100, 2, start_size=72, min_size=16
    )
    assert len(lines) == 2
    assert truncated is True


def test_fit_font_normal_not_truncated():
    draw = _draw()
    font, lines, size, truncated = composite.fit_font(
        draw, "限时优惠", 500, 2, start_size=72
    )
    assert truncated is False
    assert lines == ["限时优惠"]
