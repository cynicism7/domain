# -*- coding: utf-8 -*-
"""本地大模型调用：支持 Ollama 与 OpenAI 兼容 API（如 LM Studio）。"""

import re
from typing import Optional, Tuple


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
    max_tokens: int = 512,
    temperature: float = 0.0,
) -> str:
    """通过 OpenAI 兼容 API（如 LM Studio）请求。temperature=0 利于稳定输出 JSON。"""
    try:
        from openai import OpenAI
    except ImportError:
        return "[未安装 openai 包]"
    client = OpenAI(base_url=api_base, api_key=api_key)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
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
    max_tokens: int = 512,
    temperature: float = 0.0,
) -> tuple[str, str]:
    """
    调用本地大模型识别领域，返回 (domain_cn, domain_en)。
    未分类时会自动重试一次，以提高稳定性。
    """
    prompt = """请根据下面文献判断：是否属于「生命科学」相关（用于粗筛，只需二选一）。
可综合参考：标题、摘要、正文、作者、机构与期刊（如 xx 医院、xx 大学医学/生物/药学系、医学院、生命科学学院、生物所等均属生命科学相关）。
生命科学包含：医学、生物学、药学、农学、生物信息学、生物工程、兽医学等；其余归为非生命科学。
要求：不要使用 <think>，直接输出一行 JSON。仅两个取值：
- domain_cn 为 "生命科学" 或 "非生命科学"
- domain_en 为 "Life Science" 或 "Non-Life Science"

【文件名或标题】
%s

【文献内容（含作者与机构信息、正文片段）】
%s

只输出一行 JSON，例如：{"domain_cn": "生命科学", "domain_en": "Life Science"}""" % (
        (title or "Unknown").strip(),
        (full_text or "No Content Detected").strip(),
    )

    if provider == "mock":
        cn = _identify_domain_mock(title or "", "", full_text or "")
        en = "Life Science" if cn == "生命科学" else "Non-Life Science"
        return cn, en

    def _call() -> str:
        if provider == "openai_api":
            return ask_openai_api(
                prompt, model=model, api_base=api_base, api_key=api_key,
                max_tokens=max_tokens, temperature=temperature,
            )
        return ask_ollama(prompt, model=model)

    def _normalize_binary(domain_cn: str, domain_en: str) -> Tuple[str, str]:
        """统一为二分类：生命科学 / 非生命科学。须先判「非生命」再判「生命」，避免「非生命科学」被误判。"""
        cn = (domain_cn or "").strip()
        en = (domain_en or "").strip().lower()
        if "非生命" in cn or "non-life" in en or "non_life" in en:
            return "非生命科学", "Non-Life Science"
        if "生命科学" in cn or "life science" in en or "life" in en or "medical" in en or "bio" in en or "生命" in cn:
            return "生命科学", "Life Science"
        return "非生命科学", "Non-Life Science"

    def _parse(raw: str) -> Optional[Tuple[str, str]]:
        if not raw:
            return None
        if "</think>" in raw:
            raw = raw.split("</think>")[-1]
        try:
            for m in re.finditer(r'\{[^{}]*"domain_cn"[^{}]*"domain_en"[^{}]*\}', raw):
                try:
                    data = json.loads(m.group(0))
                    if "domain_cn" in data and "domain_en" in data:
                        return _normalize_binary(
                            data.get("domain_cn", ""), data.get("domain_en", "")
                        )
                except (json.JSONDecodeError, ValueError):
                    continue
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return _normalize_binary(
                    data.get("domain_cn", ""), data.get("domain_en", "")
                )
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
        if "|" in raw:
            parts = raw.split("|")
            if len(parts) >= 2:
                return _normalize_binary(parts[0].strip(), parts[1].strip())
        return None

    raw = _call()
    result = _parse(raw)
    if result is not None and result[0] not in ("", "未分类"):
        return result
    raw2 = _call()
    result = _parse(raw2)
    if result is not None:
        return result
    # 解析失败时根据回复文本猜测二分类（先判非生命，再判生命）
    s = raw2 or raw or ""
    r = s.lower()
    if "非生命" in s or "non-life" in r:
        return "非生命科学", "Non-Life Science"
    if "生命科学" in s or "life science" in r or "medical" in r or "biology" in r:
        return "生命科学", "Life Science"
    return "非生命科学", "Non-Life Science"


def _identify_domain_mock(title: str, abstract: str, body: str) -> str:
    """
    模拟二分类：根据标题/摘要/正文/机构关键词判断是否生命科学，用于本地验证流程。
    """
    text = (title + " " + abstract + " " + body).lower()
    life_keywords = [
        "medical", "medicine", "hospital", "生物", "医学", "药学", "生命科学",
        "biology", "biolog", "pharmacy", "pharmac", "医学院", "医学系", "生物系",
        "agriculture", "农学", "兽医", "基因", "cell", "clinical", "肿瘤", "癌症",
    ]
    for kw in life_keywords:
        if kw in text:
            return "生命科学"
    return "非生命科学"
