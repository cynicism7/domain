# 文献领域识别

通过本地大模型（Ollama 或 LM Studio 等 OpenAI 兼容 API）自动识别每篇文献的学科/领域。**领域判断依据**：标题（或文件名/元数据）、摘要、正文前两页。将「路径/文件名 + 领域」写入 SQLite 和 CSV，方便后续按领域筛选。

## 环境要求

- Python 3.8+
- 本地已运行大模型服务：
  - **Ollama**：安装 [Ollama](https://ollama.com)，并拉取模型（如 `ollama pull qwen2.5:7b`）
  - 或 **LM Studio** 等：启动本地服务器并暴露 OpenAI 兼容 API

## 安装

```bash
cd e:\domain
pip install -r requirements.txt
```

## 配置

编辑 `config.yaml`：

- **literature_dirs**：文献所在目录（可多个），程序会递归扫描子目录
- **extensions**：支持的文件类型（`.pdf`、`.docx`、`.txt` 等）
- **llm**：
  - `provider: ollama` 使用 Ollama；`provider: openai_api` 使用 LM Studio 等
  - `model`：Ollama 模型名或 API 侧模型名
  - 使用 `openai_api` 时填写 `api_base`、`api_key`
- **output**：数据库路径、是否导出 CSV 及 CSV 路径

## 本地没有大模型时如何验证

不安装 Ollama、不启动任何大模型，也可以跑通整个流程（扫描 → 提取标题/摘要/正文 → 写入数据库 → 导出 CSV → 按领域筛选）：

```bash
# 模拟模式：用简单关键词规则“模拟”领域，不请求任何 API
python main.py scan --mock
```

项目里已自带 `papers/` 下几篇示例 `.txt`，可直接执行上述命令。然后可试：

```bash
python main.py domains              # 查看出现的领域
python main.py filter 计算机科学   # 按领域筛选（示例里会匹配到 sample_computer_science.txt）
```

也可在 `config.yaml` 里把 `llm.provider` 改为 `mock`，则不加 `--mock` 时也会走模拟逻辑。

## 使用

1. **扫描并打标签**（识别每篇文献领域并写入数据库）：

   ```bash
   python main.py scan
   # 无大模型时用：python main.py scan --mock
   ```

2. **查看已记录的领域**：

   ```bash
   python main.py domains
   ```

3. **按领域筛选文献**（打印该领域下所有文献路径）：

   ```bash
   python main.py filter 计算机科学
   ```

结果会写入：

- **SQLite**：`config.yaml` 中 `output.db_path`（默认 `literature_domains.db`）
- **CSV**：若 `export_csv: true`，会导出到 `output.csv_path`，可用 Excel 等打开筛选

## 数据库结构

表 `literature_domains`：

| 字段        | 说明           |
|-------------|----------------|
| file_path   | 文献完整路径   |
| file_name   | 文件名         |
| domain      | 识别出的领域   |
| updated_at  | 最近更新时间   |

后续可按 `domain` 查询或导出筛选结果。
