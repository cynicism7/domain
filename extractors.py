# -*- coding: utf-8 -*-
"""
PDF 阶梯式识别提取器（增强稳定性版）：
1. 文本层 (PyMuPDF -> 回退到 pypdf)
2. 主 OCR (Nougat)
3. 备用 OCR (DocTR)
4. 兜底 (Tesseract)
"""

from pathlib import Path
from typing import Tuple
import os

# 阈值：如果提取文本少于此字符数，则认为需要 OCR
MIN_TEXT_THRESHOLD = 200

def extract_via_text_layer(path: Path, max_pages: int) -> str:
    """第一层：文本提取（多重备份方案）"""
    text = ""
    # 尝试方案 A: PyMuPDF (性能最好，但可能报 DLL 错误)
    try:
        import fitz
        doc = fitz.open(str(path))
        actual_max = min(len(doc), max_pages)
        for i in range(actual_max):
            text += doc[i].get_text()
        doc.close()
        if len(text.strip()) > MIN_TEXT_THRESHOLD:
            print(f"[PyMuPDF 成功] ", end="")
            return text.strip()
    except Exception as e:
        print(f" [PyMuPDF 失败: {e}] ", end="")

    # 尝试方案 B: pypdf (纯 Python，不依赖 DLL，极稳)
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        actual_max = min(len(reader.pages), max_pages)
        parts = []
        for i in range(actual_max):
            t = reader.pages[i].extract_text()
            if t: parts.append(t)
        text = "\n".join(parts)
        if len(text.strip()) > MIN_TEXT_THRESHOLD:
            print(f"[pypdf 成功] ", end="")
            return text.strip()
    except Exception as e:
        print(f" [pypdf 失败: {e}] ", end="")

    return text.strip()

def extract_via_nougat(path: Path, max_pages: int) -> str:
    """第二层：Nougat (主 OCR)"""
    try:
        import subprocess
        # 探测命令是否存在
        result = subprocess.run(
            ["nougat", str(path), "--pages", f"1-{max_pages}", "--markdown"],
            capture_output=True, text=True, encoding="utf-8", timeout=300
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""

def extract_via_doctr(path: Path, max_pages: int) -> str:
    """第三层：DocTR (备用 OCR)"""
    try:
        from doctr.io import DocumentFile
        from doctr.models import ocr_predictor
        model = ocr_predictor(pretrained=True)
        doc = DocumentFile.from_pdf(str(path))
        result = model(doc[:max_pages])
        return result.render()
    except Exception:
        pass
    return ""

def extract_via_tesseract(path: Path, max_pages: int) -> str:
    """第四层：Tesseract (兜底)"""
    try:
        import pytesseract
        import fitz  # 如果 fitz 挂了，这里尝试用 pypdf 渲染图片的方案（简化版暂用 fitz）
        from PIL import Image
        doc = fitz.open(str(path))
        text = ""
        actual_max = min(len(doc), max_pages)
        for i in range(actual_max):
            page = doc[i]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text += pytesseract.image_to_string(img, lang='eng')
        doc.close()
        return text.strip()
    except Exception:
        pass
    return ""

def extract_pdf(path: str, max_pages: int = 5) -> str:
    """阶梯逻辑入口"""
    path_obj = Path(path)
    if not path_obj.exists(): return ""

    # 1. 尝试文本层
    print(f" (Try Text Layer) ", end="", flush=True)
    text = extract_via_text_layer(path_obj, max_pages)
    if len(text) > MIN_TEXT_THRESHOLD:
        return text

    # 2. 尝试 Nougat
    print(f" (Try Nougat) ", end="", flush=True)
    text = extract_via_nougat(path_obj, max_pages)
    if len(text) > MIN_TEXT_THRESHOLD:
        print(f"[Nougat 成功] ", end="")
        return text

    # 3. 尝试 DocTR
    print(f" (Try DocTR) ", end="", flush=True)
    text = extract_via_doctr(path_obj, max_pages)
    if len(text) > MIN_TEXT_THRESHOLD:
        print(f"[DocTR 成功] ", end="")
        return text

    # 4. 尝试 Tesseract
    print(f" (Try Tesseract) ", end="", flush=True)
    text = extract_via_tesseract(path_obj, max_pages)
    
    # 记录结果供调试
    if text.strip():
        debug_txt = path_obj.with_suffix(path_obj.suffix + ".ocr.txt")
        try:
            debug_txt.write_text(text, encoding="utf-8")
        except: pass
    else:
        print("[所有识别层均告失败] ", end="")
            
    return text

def extract_title_abstract_body(file_path: str, **kwargs) -> Tuple[str, str, str]:
    """适配接口"""
    path = Path(file_path)
    full_text = extract_pdf(file_path, max_pages=5)
    return path.name, full_text, ""
