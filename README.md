# 文献领域识别（强制 OCR + 本地 LM Studio）

本项目用于批量扫描本地 PDF 英文文献，**强制使用 OCR** 识别前几页文字（不依赖 PDF 是否可复制），并将识别出的内容（标题/摘要/正文前两页附近文本）发送给你本地部署在 **LM Studio** 的大模型进行学术领域判定，最终将结果写入 SQLite 并导出 CSV，方便后续筛选。

## 功能概览

- 扫描配置目录下的 PDF（递归子目录）
- PDF 前 5 页渲染为图片并 OCR（PaddleOCR，英文）
- 从 OCR 文本中切分摘要与正文片段（基于 Abstract / Introduction 等关键词）
- 调用本地 LM Studio（OpenAI 兼容 API）识别领域标签
- 写入数据库 `literature_domains.db`，并导出 `literature_domains.csv`

## 环境要求

- Windows / macOS / Linux
- Python 3.9+（推荐 3.10/3.11）
- LM Studio 已启动本地 Server，并开启 OpenAI Compatible API

## 安装依赖

在项目目录执行：

```bash
pip install -r requirements.txt
```

如果你是首次使用 OCR，通常还需要安装：

- `pymupdf`（用于 PDF 渲染）
- `paddlepaddle`、`paddleocr`（OCR 引擎）
- `opencv-python-headless`（OCR 依赖）

如果你当前 `requirements.txt` 未包含上述 OCR 依赖，可直接安装：

```bash
pip install pymupdf paddlepaddle paddleocr opencv-python-headless
```

说明：

- 默认使用 CPU 推理（`use_gpu=False`）。如需 GPU，请自行安装对应的 PaddlePaddle GPU 版本并调整代码。
- 若你机器上有多个项目依赖较复杂，建议使用 venv 虚拟环境隔离。

## 配置（config.yaml）

编辑 `config.yaml`，你主要需要改两项：

1. **文献目录**：`literature_dirs`
2. **LM Studio 模型与接口**：`llm`

示例：

```yaml
literature_dirs:
  - "D:/MyPapers"
  - "E:/Literature/PDFs"

extensions:
  - ".pdf"

llm:
  provider: "openai_api"
  model: "DeepSeek-R1-0528-Qwen3-8B"
  api_base: "http://localhost:1234/v1"
  api_key: "lm-studio"

max_chars_for_llm: 3000

output:
  db_path: "./literature_domains.db"
  export_csv: True
  csv_path: "./literature_domains.csv"
```

参数说明：

- `literature_dirs`：文献目录列表（可多个），程序会递归扫描子目录
- `extensions`：建议只保留 `.pdf`
- `llm.provider`：使用 LM Studio 时设为 `openai_api`
- `llm.model`：LM Studio 中实际加载并对外提供的模型名（需与 LM Studio 一致）
- `llm.api_base`：LM Studio OpenAI 兼容 API 地址（常见 `http://localhost:1234/v1`）
- `max_chars_for_llm`：发给大模型的最大字符数（越大越慢，但信息更全）

## 使用方法

### 1) 扫描并打标签

```bash
python main.py scan
```

运行后会逐个输出：

- 当前处理的文件
- 模型返回的领域标签

并写入：

- SQLite：`output.db_path`（默认 `./literature_domains.db`）
- CSV：`output.csv_path`（默认 `./literature_domains.csv`）

### 2) 查看已记录的领域

```bash
python main.py domains
```

### 3) 按领域筛选

```bash
python main.py filter 计算机科学
```

会打印该领域下的所有文献路径。

## 输出说明

CSV 文件列：

- `file_path`：文献绝对路径
- `file_name`：文件名
- `domain`：识别出的领域标签
- `updated_at`：更新时间

## 常见问题

### 1) 识别速度慢

- OCR 是主要耗时步骤（尤其是扫描版 PDF）。
- 本项目已将 OCR 引擎做成进程内复用（不会每个 PDF 重新初始化一次）。
- 你可以减少 OCR 页数（目前固定前 5 页；如需改成 3 页或 8 页我可以继续帮你改）。

### 2) LM Studio 请求失败 / model 不存在

- 请确认 `config.yaml` 中 `llm.model` 与 LM Studio 暴露的模型名一致。
- 请确认 LM Studio Server 已启动，并且 `api_base` 端口正确。

### 3) PDF OCR 文本质量一般

- 可尝试提高渲染分辨率（当前 `Matrix(2.0, 2.0)`）。
- 文献为双栏排版时，OCR 可能出现顺序错乱；后续可加版面分析优化。
