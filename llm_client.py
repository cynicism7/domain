# -*- coding: utf-8 -*-
"""本地大模型调用：支持 Ollama 与 OpenAI 兼容 API（如 LM Studio）。"""

import re
from typing import Optional


def _normalize_domain(raw: str) -> str:
    """从模型输出中提取单一领域标签，去除多余符号和换行。"""
    if not raw or not isinstance(raw, str):
        return "未分类"
    s = raw.strip()
    # 取第一行或第一个逗号/句号前
    for sep in ("\n", "，", "。", ",", "."):
        if sep in s:
            s = s.split(sep)[0].strip()
    # 去掉常见前缀和引号
    s = re.sub(r"^(领域|学科|类别|领域：|学科：|类别：)\s*", "", s, flags=re.I)
    s = s.strip('"\' \t')
    return s if s else "未分类"


def ask_ollama(prompt: str, model: str = "qwen2.5:7b", timeout: int = 120) -> str:
    """通过 Ollama 本地 API 请求，返回模型回复文本。"""
    try:
        import ollama
    except ImportError:
        try:
            import requests
            r = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=timeout,
            )
            r.raise_for_status()
            return (r.json().get("response") or "").strip()
        except Exception as e:
            return f"[Ollama 请求失败: {e}]"
    try:
        resp = ollama.generate(model=model, prompt=prompt)
        return (resp.get("response") or "").strip()
    except Exception as e:
        return f"[Ollama 请求失败: {e}]"


def ask_openai_api(
    prompt: str,
    model: str = "local-model",
    api_base: str = "http://localhost:1234/v1",
    api_key: str = "not-needed",
    timeout: int = 120,
) -> str:
    """通过 OpenAI 兼容 API（如 LM Studio）请求。"""
    try:
        from openai import OpenAI
    except ImportError:
        return "[未安装 openai 包]"
    client = OpenAI(base_url=api_base, api_key=api_key)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            timeout=timeout,
        )
        msg = resp.choices[0].message.content if resp.choices else ""
        return (msg or "").strip()
    except Exception as e:
        return f"[API 请求失败: {e}]"


import json


def identify_domain(
    title: str,
    full_text: str,
    *,
    provider: str = "ollama",
    model: str = "qwen2.5:7b",
    api_base: str = "http://localhost:1234/v1",
    api_key: str = "not-needed",
) -> tuple[str, str]:
    """
    调用本地大模型识别领域，返回 (domain_cn, domain_en)。
    """
    prompt = """请根据下面文献的内容，判断其所属的学术领域。
要求：
1. 返回一个标准的学术领域名称（如：计算机科学/Computer Science, 生物信息学/Bioinformatics）。
2. 必须以 JSON 格式返回，包含 "domain_cn" 和 "domain_en" 两个字段。
3. 领域名称要准确、专业。

【文件名或标题 / Title or Filename】
%s

【前五页OCR全文 / OCR Full Text (First 5 Pages)】
%s

JSON Output:""" % (
        (title or "Unknown").strip(),
        (full_text or "No Content Detected").strip(),
    )

    if provider == "mock":
        return _identify_domain_mock(title or "", "", full_text or ""), "Test Domain"
    
    raw = ""
    if provider == "openai_api":
        raw = ask_openai_api(prompt, model=model, api_base=api_base, api_key=api_key)
    else:
        raw = ask_ollama(prompt, model=model)
    
    # 解析 JSON
    try:
        # 寻找 JSON 块
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return data.get("domain_cn", "未分类"), data.get("domain_en", "Unclassified")
    except:
        pass
    
    # 兜底：简单切割
    if "|" in raw:
        parts = raw.split("|")
        return parts[0].strip(), parts[1].strip()
    
    return _normalize_domain(raw), "Unclassified"


def _identify_domain_mock(title: str, abstract: str, body: str) -> str:
    """
    模拟领域识别：不调用任何大模型，根据标题/摘要/正文做简单关键词匹配，
    用于本地无大模型时验证程序流程（扫描、提取、入库、导出、筛选）。
    """
    text = (title + " " + abstract + " " + body).lower()
    # 简单关键词 -> 领域（可自行扩展）
    rules = [
        ("network", "计算机科学"),
        ("deep learning", "计算机科学"),
        ("algorithm", "计算机科学"),
        ("生物", "生物学"),
        ("基因", "生物学"),
        ("经济", "经济学"),
        ("金融", "经济学"),
        ("物理", "物理学"),
        ("医学", "医学"),
        ("法律", "法学"),
    ]
    for kw, domain in rules:
        if kw in text:
            return domain
    # 无匹配时按标题哈希得到几种固定标签，便于测试「按领域筛选」
    n = (hash(title or "x") % 5) + 1
    return f"测试领域-{n}"
