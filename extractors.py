# -*- coding: utf-8 -*-
"""
PDF 提取器（RAG 式分块 + 整合，不存文件）：
1. 从 PDF 取全文（文本层优先，不足时 OCR 兜底）
2. 按 RAG 思路分块（固定长度 + 重叠）
3. 将碎片文本整合为一段，供大模型识别领域（不写入任何文件）
"""

from pathlib import Path
from typing import Tuple, List

# 文本过少则视为需 OCR
MIN_TEXT_THRESHOLD = 200

# 默认分块参数（与常见 RAG 配置一致：按字符近似等价于 ~300–500 token 的块）
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 100

# 文献开头通常为标题、作者、单位、期刊等，单独保留供 AI 综合判断领域（如 xx 医院、xx 大学医学系）
AUTHOR_SECTION_CHARS = 1200


def _extract_text_layer(path: Path, max_pages: int) -> str:
    """文本层提取：优先 PyMuPDF，回退 pypdf。"""
    text = ""
    try:
        import fitz
        doc = fitz.open(str(path))
        n = min(len(doc), max_pages)
        for i in range(n):
            text += doc[i].get_text()
        doc.close()
        if text.strip():
            return text.strip()
    except Exception:
        pass

    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        n = min(len(reader.pages), max_pages)
        parts = [reader.pages[i].extract_text() for i in range(n) if reader.pages[i].extract_text()]
        if parts:
            return "\n".join(parts).strip()
    except Exception:
        pass
    return ""


def _extract_ocr_fallback(path: Path, max_pages: int) -> str:
    """OCR 兜底：用 PyMuPDF 渲染页面 + Tesseract 识别。"""
    try:
        import fitz
        import pytesseract
        from PIL import Image
        doc = fitz.open(str(path))
        text = ""
        n = min(len(doc), max_pages)
        for i in range(n):
            page = doc[i]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text += pytesseract.image_to_string(img, lang="eng+chi_sim")
        doc.close()
        return text.strip()
    except Exception:
        pass
    return ""


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[str]:
    """
    RAG 式分块：按字符数切分，块间带重叠，尽量在句/行边界切割。
    """
    if not text or chunk_size <= 0:
        return []
    text = text.strip()
    if len(text) <= chunk_size:
        return [text] if text else []

    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break
        # 在句号、换行或空格处截断，避免截断单词/中文
        segment = text[start:end]
        for sep in ("\n\n", "\n", "。", ".", " ", ""):
            idx = segment.rfind(sep)
            if idx > chunk_size // 2:
                end = start + idx + (len(sep) if sep else 0)
                break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - min(overlap, chunk_size - 1)
    return chunks


def merge_chunks_for_llm(
    chunks: List[str],
    max_chars: int,
    separator: str = "\n\n",
) -> str:
    """
    将分块文本整合为一段，总长度不超过 max_chars，供 LLM 使用。
    不写入任何文件。
    """
    if not chunks:
        return ""
    merged = separator.join(chunks)
    if len(merged) <= max_chars:
        return merged
    # 从开头截断到 max_chars，尽量在句末截断
    truncated = merged[:max_chars]
    for sep in ("\n", "。", ".", " "):
        last = truncated.rfind(sep)
        if last > max_chars // 2:
            truncated = truncated[: last + 1]
            break
    return truncated.strip()


def extract_pdf_text(path: str, max_pages: int = 10) -> str:
    """
    从 PDF 提取全文：先文本层，不足时 OCR 兜底。
    不写入任何中间文件。
    """
    p = Path(path)
    if not p.exists():
        return ""

    raw = _extract_text_layer(p, max_pages)
    if len(raw) >= MIN_TEXT_THRESHOLD:
        return raw
    ocr = _extract_ocr_fallback(p, max_pages)
    return ocr if ocr else raw


def _split_author_and_body(full_text: str, author_chars: int = AUTHOR_SECTION_CHARS) -> Tuple[str, str]:
    """
    将文献开头切出「作者与机构」段落（通常含标题、作者、单位、期刊等），
    便于 AI 结合机构信息（如 xx 医院、xx 大学医学系）综合判断领域。
    """
    text = full_text.strip()
    if not text:
        return "", ""
    if len(text) <= author_chars:
        return text, ""
    # 尽量在段落边界截断作者区
    head = text[:author_chars]
    for sep in ("\n\n", "\n", "。", "."):
        idx = head.rfind(sep)
        if idx > author_chars // 2:
            head = text[: idx + len(sep)].strip()
            break
    body = text[len(head) :].strip()
    return head, body


def extract_title_abstract_body(
    file_path: str,
    abstract_max: int = 1500,
    body_pages_chars: int = 2400,
    max_chars_for_llm: int = 3000,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    author_section_chars: int = AUTHOR_SECTION_CHARS,
    **kwargs,
) -> Tuple[str, str, str]:
    """
    对 PDF 做 RAG 式处理：取文 → 拆出作者/机构段 → 正文分块 → 整合给 AI，不存文件。
    返回 (标题/文件名, 整合内容, "")。整合内容含【作者与机构信息】与【正文与摘要片段】，
    便于 AI 结合作者、单位、期刊等综合判断（如 xx 医院、xx 大学医学系 → 生命科学）。
    """
    path = Path(file_path)
    if path.suffix.lower() != ".pdf":
        return path.name, "", ""

    max_pages = 15
    full_text = extract_pdf_text(str(path), max_pages=max_pages)
    if not full_text.strip():
        return path.name, "", ""

    # 1) 单独保留文献开头的作者与机构信息（标题、作者、单位、期刊等）
    author_section, body_text = _split_author_and_body(full_text, author_chars=author_section_chars)
    prefix = "【作者与机构信息】\n" + author_section + "\n\n【正文与摘要片段】\n"
    budget = max(0, max_chars_for_llm - len(prefix))

    # 2) 正文分块并合并，总长不超过 budget
    if body_text:
        chunks = chunk_text(body_text, chunk_size=chunk_size, overlap=chunk_overlap)
        body_merged = merge_chunks_for_llm(chunks, max_chars=budget)
    else:
        body_merged = ""

    content = prefix + body_merged
    return path.name, content.strip(), ""
