# 文献领域识别（生命科学 / 非生命科学 二分类）

批量扫描本地 PDF 文献，提取文本（含**作者与机构信息**）后送交本地大模型，判断是否属于**生命科学**相关，结果写入 SQLite 并导出 CSV，便于筛选生命科学文献。

## 功能概览

- **扫描**：递归扫描配置目录下的 PDF（可配置扩展名）
- **提取**：优先从 PDF 文本层取文（PyMuPDF / pypdf），不足时使用 Tesseract OCR 兜底；按 RAG 思路分块后整合，**显式包含「作者与机构信息」**（标题、作者、单位、期刊等），便于结合 xx 医院、xx 大学医学系等判断
- **分类**：调用本地大模型（LM Studio / Ollama，OpenAI 兼容 API）做**二分类**：**生命科学** 或 **非生命科学**（医学、生物、药学、农学、生物信息等归为生命科学，其余为非生命科学）
- **输出**：写入 `literature_domains.db`，并导出 `literature_domains.csv`；支持按领域筛选（如只列生命科学文献）

## 环境要求

- Python 3.9+
- 本地大模型服务：**LM Studio**（推荐，OpenAI 兼容 API）或 **Ollama**

## 安装依赖

```bash
pip install -r requirements.txt
```

- **PDF 文本**：`pymupdf`、`pypdf`（取文本层）
- **OCR 兜底**（可选）：若 PDF 无文本层或文字过少，需安装 `pytesseract` 并安装 [Tesseract](https://github.com/tesseract-ocr/tesseract) 本体
- **大模型调用**：`openai`（LM Studio）、`ollama`（Ollama）

建议在 venv 中安装以免与其它项目冲突。

## 配置（config.yaml）

```yaml
literature_dirs:
  - "./papers"
extensions:
  - ".pdf"

llm:
  provider: "openai_api"        # 或 ollama
  model: "DeepSeek-R1-0528-Qwen3-8B"
  api_base: "http://127.0.0.1:1234/v1"
  api_key: "lm-studio"
  max_tokens: 512               # R1 等思考型模型需 512 以容纳 <think>+JSON
  temperature: 0.0

max_chars_for_llm: 2500        # 送交模型的字符上限，减小可提速

output:
  db_path: "./literature_domains.db"
  export_csv: True
  csv_path: "./literature_domains.csv"
```

| 项 | 说明 |
|----|------|
| `literature_dirs` | 文献根目录列表，会递归扫描子目录 |
| `extensions` | 参与扫描的扩展名，通常只保留 `.pdf` |
| `llm.provider` | `openai_api`（LM Studio）或 `ollama` |
| `llm.model` | 与 LM Studio / Ollama 中加载的模型名一致 |
| `llm.api_base` | LM Studio 的 API 地址，常见 `http://127.0.0.1:1234/v1` |
| `llm.max_tokens` | 生成 token 上限；思考型模型建议 512，否则可 256 |
| `llm.temperature` | 建议 0 以稳定输出 JSON |
| `max_chars_for_llm` | 送交的文献内容最大字符数，适当减小可加快推理 |

## 使用方法

### 扫描并打标签

```bash
python main.py scan
```

会逐个处理 PDF，打印「送交 N 字」及识别结果（生命科学 / 非生命科学），并写入数据库与 CSV。

### 模拟模式（不调用大模型）

```bash
python main.py scan --mock
```

按关键词规则模拟「生命科学 / 非生命科学」，用于验证流程。

### 查看已记录的领域

```bash
python main.py domains
```

### 按领域筛选文献（筛出生命科学）

```bash
python main.py filter 生命科学
```

会列出所有被标为「生命科学」的文献路径。筛「非生命科学」则：

```bash
python main.py filter 非生命科学
```

## 输出说明

- **SQLite**（`output.db_path`）：表内为 `file_path`、`file_name`、`domain_cn`、`domain_en`、`updated_at`
- **CSV**（`output.csv_path`）：同上字段，便于 Excel 打开

领域取值仅两种：**生命科学** / **非生命科学**（及对应英文 Life Science / Non-Life Science）。

## 常见问题

**Q: 日志里看到 "Truncated in logs"，送交的内容是否被截断？**  
A: 那是 LM Studio 日志的显示截断，实际请求里送交的是完整内容。程序会打印「(送交 N 字)」，N 即为本次送交的字符数。

**Q: 识别速度慢？**  
A: 可适当减小 `max_chars_for_llm`（如 2000）；非思考型模型可将 `llm.max_tokens` 设为 256。单篇耗时主要来自模型推理。

**Q: 结果有时是「生命科学」有时是「未分类」？**  
A: 已通过 `temperature=0`、未分类时自动重试一次、以及二分类归一化逻辑减少该情况。若仍出现，请确认 `max_tokens` 足够（思考型模型建议 512）。

**Q: LM Studio 请求失败 / 模型不存在？**  
A: 确认 `config.yaml` 中 `llm.model`、`llm.api_base` 与 LM Studio 中一致，且 Server 已启动。
