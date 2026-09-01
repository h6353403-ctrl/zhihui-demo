"""健壮的 JSON 提取工具。

模型输出往往不是干净的 JSON，常见问题：
- 被 ```json ... ``` markdown 代码块包裹
- 前后夹杂解释文字
- 一次输出多个 JSON 对象（只需取第一个）
- 嵌套对象
- 尾逗号、// 或 # 注释

本模块提供 `extract_json`，用「平衡括号扫描」定位第一个完整 JSON 片段，
再做轻量修复后交给标准库 json 解析。
"""
import json
import re


def _strip_fences(text: str) -> str:
    """去掉 markdown 代码块标记（```json 与 ```）。"""
    return re.sub(r"```(?:json)?|```", "", text or "").strip()


def _scan_balanced(text: str) -> str:
    """从第一个 '{' 开始扫描，返回第一个括号配平的 JSON 片段。

    正确处理字符串内的 '{'/'}'、转义字符与嵌套对象，避免被内层括号或
    多个 JSON 对象干扰。
    """
    start = text.find("{")
    if start < 0:
        raise ValueError("模型未返回 JSON 对象：" + text[:200])

    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    raise ValueError("JSON 对象未闭合：" + text[start : start + 200])


def _strip_comments(fragment: str) -> str:
    """去掉字符串外的 // 与 # 注释（含整行与行尾注释）。

    逐字符扫描并跟踪字符串状态，避免误伤字符串内的 '#'（如颜色值 #fff）
    或 '//'（如 http://）。
    """
    out = []
    in_str = False
    escaped = False
    i = 0
    n = len(fragment)
    while i < n:
        ch = fragment[i]
        if in_str:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            i += 1
            continue

        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == "#" or (ch == "/" and i + 1 < n and fragment[i + 1] == "/"):
            # 行尾注释：跳过直到换行符（保留换行）
            while i < n and fragment[i] != "\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _repair_common_issues(fragment: str) -> str:
    """修复模型输出中最常见的两类格式问题：注释、尾逗号。

    不做单引号替换等高风险操作，避免误伤字符串内容。
    """
    fragment = _strip_comments(fragment)
    # 尾逗号：, 后紧跟空白再跟 } 或 ]
    fragment = re.sub(r",(\s*[}\]])", r"\1", fragment)
    return fragment


def extract_json(text):
    """从任意模型输出中提取并解析第一个 JSON 对象。

    失败时抛出 ValueError，错误信息附带失败原因与片段，便于排障。
    """
    clean = _strip_fences(text)
    fragment = _scan_balanced(clean)

    try:
        return json.loads(fragment)
    except json.JSONDecodeError as first_err:
        repaired = _repair_common_issues(fragment)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            raise ValueError(
                f"JSON 解析失败：{first_err.msg}（位置 {first_err.pos}）；片段：{fragment[:200]}"
            )
