import pytest

from app.services.jsonutil import extract_json


def test_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_markdown_fence():
    text = '```json\n{"brand": "花漾"}\n```'
    assert extract_json(text) == {"brand": "花漾"}


def test_surrounding_text():
    text = '好的，以下是解析结果：\n{"brand": "花漾"}\n希望有帮助。'
    assert extract_json(text) == {"brand": "花漾"}


def test_nested_object():
    text = '{"a": {"b": [1, 2, {"c": "}"}]}}'
    assert extract_json(text) == {"a": {"b": [1, 2, {"c": "}"}]}}


def test_multiple_objects_takes_first():
    text = '{"a": 1}\n{"b": 2}'
    assert extract_json(text) == {"a": 1}


def test_brace_inside_string():
    text = '{"s": "包含{花括号}的字符串"}'
    assert extract_json(text) == {"s": "包含{花括号}的字符串"}


def test_escaped_quote():
    text = '{"s": "带\\"引号\\""}'
    assert extract_json(text) == {"s": '带"引号"'}


def test_trailing_comma():
    text = '{"a": 1, "b": [1, 2,], "c": {"d": 3,},}'
    assert extract_json(text) == {"a": 1, "b": [1, 2], "c": {"d": 3}}


def test_comment_lines():
    text = '{\n// 注释\n"a": 1, # 行尾\n}'
    # # 整行注释会被去掉；行尾 # 不处理（json 里 # 非法），此处仅验证整行注释
    assert extract_json(text) == {"a": 1}


def test_no_brace_raises():
    with pytest.raises(ValueError, match="未返回 JSON"):
        extract_json("完全没有 json")


def test_unclosed_raises():
    with pytest.raises(ValueError, match="未闭合"):
        extract_json('{"a": 1')


def test_invalid_json_raises_with_snippet():
    with pytest.raises(ValueError, match="解析失败"):
        extract_json('{"a": }')
