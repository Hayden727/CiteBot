# CiteBot

智能文献引用助手，自动分析 LaTeX 文档内容，搜索学术数据库，生成包含相关文献的 BibTeX 文件。

## 功能特性

- **LaTeX 文档解析** — 从 `.tex` 文件中提取标题、摘要、章节结构和已有引用
- **集成关键词提取** — 融合 KeyBERT（语义）、YAKE（统计）和 spaCy（NLP）三种方法，关键词识别更准确
- **多源并行搜索** — 同时查询 OpenAlex、Semantic Scholar、PubMed、arXiv 和 BioRxiv
- **智能排序** — 基于关键词匹配度、引用量、时效性和摘要相似度的综合评分
- **自动去重** — 基于 DOI 和模糊标题匹配消除重复结果
- **BibTeX 生成** — 优先通过 DOI 内容协商获取权威 BibTeX，元数据生成兜底
- **引用插入** — 可选功能：在文档中插入 `\cite{}` 命令（写入 `.cited.tex`，不覆盖原文件）

## 快速上手

### 环境要求

- [Anaconda](https://www.anaconda.com/) 或 [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- Python 3.11+

### 安装

```bash
# 创建并激活 conda 环境
conda create -n citebot python=3.11 -y
conda activate citebot

# 安装 CiteBot
git clone <repo-url> && cd CiteBot
pip install -e .
```

### 配置（可选但推荐）

复制示例环境文件并填入 API 密钥，以获得更高的请求速率：

```bash
cp .env.example .env
```

可用的密钥：

| 变量 | 用途 |
|------|------|
| `SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar API 访问 |
| `PUBMED_API_KEY` | PubMed/NCBI 访问 |
| `OPENALEX_API_KEY` | OpenAlex 高速访问 |
| `CROSSREF_EMAIL` | CrossRef 礼貌池 |
| `OPENCITE_EMAIL` | API 请求头中的联系邮箱 |

不配置 API 密钥也可以使用，但请求频率会受到更严格的限制。

## 使用方法

### 基本用法

```bash
# 为论文生成 30 篇参考文献
citebot paper.tex --num-refs 30 --output references.bib

# 简写形式
citebot paper.tex -n 30 -o refs.bib
```

### 进阶用法

```bash
# 自动在文档中插入 \cite{} 命令
citebot paper.tex -n 50 -o refs.bib --insert-cites

# 限定年份范围
citebot paper.tex --year-from 2020 --year-to 2025

# 指定数据源
citebot paper.tex --sources openalex,s2,arxiv

# 详细输出，显示文献排名表格
citebot paper.tex -n 20 -o refs.bib -v
```

### 全部选项

| 选项 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--num-refs` | `-n` | 30 | 查找的参考文献数量 |
| `--output` | `-o` | `references.bib` | 输出 `.bib` 文件路径 |
| `--insert-cites` | | 关闭 | 在 `.tex` 文件中插入 `\cite{}` |
| `--year-from` | | 无 | 最早发表年份 |
| `--year-to` | | 无 | 最晚发表年份 |
| `--sources` | | 全部 | 逗号分隔：`openalex,s2,pubmed,arxiv,biorxiv` |
| `--keywords` | `-k` | 15 | 提取的关键词数量 |
| `--verbose` | `-v` | 关闭 | 显示详细输出 |

## 工作原理

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  解析    │───>│  提取    │───>│  搜索    │───>│  排序    │───>│  生成    │
│  .tex    │    │  关键词  │    │  文献    │    │  筛选    │    │  .bib    │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                                      │
                                                                      v
                                                               ┌──────────┐
                                                               │ (插入    │
                                                               │  引用)   │
                                                               └──────────┘
```

1. **解析** — 读取 `.tex` 文件，提取标题、摘要、章节结构和纯文本
2. **提取关键词** — 三种提取器集成运行（KeyBERT、YAKE、spaCy），加权合并结果
3. **搜索文献** — 根据关键词构建 3-5 个不同粒度的查询，通过 OpenCite 并行搜索学术数据库
4. **排序筛选** — 去重后对每篇文献综合评分：关键词匹配度（40%）、引用量（25%）、时效性（20%）、摘要相似度（15%）
5. **生成 BibTeX** — 优先通过 DOI 获取权威 BibTeX 条目，获取失败则基于元数据生成
6. **插入引用**（可选）— 在文档副本的相关位置添加 `\cite{}` 命令

## 项目结构

```
CiteBot/
├── citebot/
│   ├── __init__.py              包初始化
│   ├── types.py                 不可变数据类型 + 异常层级
│   ├── config.py                配置管理（OpenCite + CLI 参数）
│   ├── latex_parser.py          .tex 文件解析
│   ├── keyword_extractor.py     集成关键词提取
│   ├── literature_searcher.py   异步多源搜索
│   ├── filter_ranker.py         去重 + 综合评分排序
│   ├── bib_generator.py         BibTeX 生成 + 校验
│   ├── cite_inserter.py         可选引用插入
│   ├── pipeline.py              流水线编排
│   └── main.py                  CLI 入口
├── tests/                       72 个单元测试 + 集成测试
├── pyproject.toml               构建配置
├── requirements.txt             锁定的依赖版本
└── .env.example                 API 密钥模板
```

## 开发

### 运行测试

```bash
conda activate citebot
python -m pytest tests/ -v --cov=citebot --cov-report=term-missing
```

### 数据源

| 数据源 | 覆盖范围 | 访问方式 |
|--------|----------|----------|
| [OpenAlex](https://openalex.org/) | 2.5 亿+ 篇论文，覆盖所有学科 | 开放，无需密钥 |
| [Semantic Scholar](https://www.semanticscholar.org/) | 2 亿+ 篇论文，侧重计算机科学和生物医学 | 建议申请免费 API 密钥 |
| [PubMed](https://pubmed.ncbi.nlm.nih.gov/) | 3600 万+ 条生物医学引文 | 建议申请免费 API 密钥 |
| [arXiv](https://arxiv.org/) | 200 万+ 篇 STEM 领域预印本 | 开放 |
| [BioRxiv](https://www.biorxiv.org/) | 生物学预印本 | 开放 |

## 许可证

MIT
