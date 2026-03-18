<a id="readme-top"></a>

<!-- 项目 LOGO -->
<div align="center">
  <img src="assets/profile.png" alt="CiteBot" width="400">
</div>

<br />

<!-- 项目徽章 -->
<div align="center">

[![Python][python-shield]][python-url]
[![License][license-shield]][license-url]
[![Claude Code][claude-shield]][claude-url]

</div>

<div align="center">

  <h3 align="center">CiteBot</h3>

  <p align="center">
    智能文献引用助手，自动分析 LaTeX 文档内容，搜索学术数据库，生成包含相关文献的 BibTeX 文件。
    <br />
    <br />
    <a href="https://github.com/Hayden727/CiteBot/issues/new?labels=bug">报告 Bug</a>
    &middot;
    <a href="https://github.com/Hayden727/CiteBot/issues/new?labels=enhancement">功能建议</a>
    &middot;
    <a href="README.md">English</a>
  </p>
</div>

<!-- 目录 -->
<details>
  <summary>目录</summary>
  <ol>
    <li><a href="#关于本项目">关于本项目</a></li>
    <li><a href="#功能特性">功能特性</a></li>
    <li>
      <a href="#快速上手">快速上手</a>
      <ul>
        <li><a href="#环境要求">环境要求</a></li>
        <li><a href="#安装">安装</a></li>
        <li><a href="#配置">配置</a></li>
      </ul>
    </li>
    <li>
      <a href="#使用方法">使用方法</a>
      <ul>
        <li><a href="#基本用法">基本用法</a></li>
        <li><a href="#进阶用法">进阶用法</a></li>
        <li><a href="#全部选项">全部选项</a></li>
      </ul>
    </li>
    <li><a href="#工作原理">工作原理</a></li>
    <li><a href="#数据源">数据源</a></li>
    <li><a href="#测试">测试</a></li>
    <li><a href="#项目结构">项目结构</a></li>
    <li><a href="#参与贡献">参与贡献</a></li>
    <li><a href="#许可证">许可证</a></li>
    <li><a href="#致谢">致谢</a></li>
  </ol>
</details>

---

## 关于本项目

CiteBot 将论文写作中最繁琐的文献调研与引用流程自动化。只需提供你的 `.tex` 文件和目标引用数量，它会自动完成：解析文档内容、理解研究主题、并行搜索多个学术数据库、按相关性排序、生成可直接使用的 `.bib` 文件。

### 技术栈

[![Python][python-shield]][python-url]
[![OpenCite][opencite-shield]][opencite-url]
[![DeepSeek][deepseek-shield]][deepseek-url]
[![Click][click-shield]][click-url]

## 功能特性

- **多文件项目支持** &mdash; 传入主 `.tex` 文件或项目目录，自动追踪 `\input{}`/`\include{}` 解析整个论文项目。生成统一的 `.bib` 文件，并在每个章节文件中插入引用
- **LaTeX 文档解析** &mdash; 从 `.tex` 文件中提取标题、摘要、章节结构和已有引用（支持 `\chapter`、`\section`、中文文档）
- **LLM 驱动的关键词提取** &mdash; 优先使用 DeepSeek/OpenAI 理解文档语义，精准提取英文学术术语；大型项目按章节分块提取后合并（支持 100+ 关键词）。未配置 LLM 时回退到 NLP 集成方案（KeyBERT + YAKE + spaCy）
- **多源并行搜索** &mdash; 通过 OpenCite 同时查询 OpenAlex、Semantic Scholar、PubMed、arXiv 和 BioRxiv
- **智能排序** &mdash; 综合评分：关键词匹配度（40%）、引用量（25%）、时效性（20%）、摘要相似度（15%）
- **自动去重** &mdash; 基于 DOI 和模糊标题匹配消除重复结果
- **BibTeX 生成** &mdash; 优先通过 DOI 内容协商获取权威 BibTeX，元数据生成兜底
- **引用插入** &mdash; 可选功能：在文档中插入 `\cite{}` 命令（写入 `.cited.tex`，不覆盖原文件）。多文件项目中每个章节文件各自生成 `.cited.tex`

## 快速上手

### 环境要求

- [Anaconda](https://www.anaconda.com/) 或 [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- Python 3.11+

### 安装

```bash
conda create -n citebot python=3.11 -y
conda activate citebot

git clone https://github.com/Hayden727/CiteBot.git
cd CiteBot
pip install -e .
```

### 配置

复制示例环境文件并填入 API 密钥：

```bash
cp .env.example .env
```

| 变量 | 用途 | 是否必需 |
|------|------|----------|
| `DEEPSEEK_API_KEY` | LLM 关键词提取（中文文档效果极佳） | 推荐 |
| `OPENAI_API_KEY` | 替代 LLM 方案（可配合 `OPENAI_BASE_URL` + `OPENAI_MODEL` 使用兼容 API） | 可选 |
| `SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar API 访问（免费，CS 方向推荐） | 推荐 |
| `OPENCITE_EMAIL` | OpenAlex 礼貌池联系邮箱（提高请求速率） | 推荐 |
| `CROSSREF_EMAIL` | CrossRef 礼貌池 | 可选 |
| `PUBMED_API_KEY` | PubMed/NCBI 访问 | 可选 |

> 不配置 API 密钥也可以使用，但关键词质量和搜索速率会受影响。

## 使用方法

### 基本用法

```bash
# 单文件论文：生成 30 篇参考文献
citebot paper.tex --num-refs 30 --output references.bib

# 多文件毕业论文：传入主文件，自动追踪 \input/\include
citebot main.tex -n 100 -o references.bib -k 50
```

### 进阶用法

```bash
# 在每个章节文件中插入 \cite{}（生成 .cited.tex 副本）
citebot main.tex -n 100 -o refs.bib --insert-cites

# 传入目录，自动查找主 .tex 文件
citebot thesis/ -n 100 -o refs.bib

# 限定年份范围
citebot paper.tex --year-from 2020 --year-to 2025

# 指定数据源（CS 方向推荐）
citebot paper.tex --sources s2,openalex,arxiv

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

1. **解析** &mdash; 读取 `.tex` 文件（或目录），自动追踪 `\input{}`/`\include{}` 解析多文件项目，提取所有文件的标题、摘要和章节内容
2. **提取关键词** &mdash; 优先使用 LLM（DeepSeek/OpenAI）语义理解提取关键词；多文件项目按章节分块提取后合并（支持 100+ 关键词）。无 LLM 时回退到 NLP 集成方案
3. **搜索文献** &mdash; 根据关键词数量自动扩展查询数，通过 OpenCite 并行搜索学术数据库
4. **排序筛选** &mdash; 去重后对每篇文献综合评分：关键词匹配度（40%）、引用量（25%）、时效性（20%）、摘要相似度（15%）
5. **生成 BibTeX** &mdash; 优先通过 DOI 获取权威 BibTeX 条目，获取失败则基于元数据生成
6. **插入引用**（可选）&mdash; 在每个文件的相关位置添加 `\cite{}` 命令（各自生成 `.cited.tex` 副本）

## 数据源

| 数据源 | 覆盖范围 | 访问方式 |
|--------|----------|----------|
| [OpenAlex](https://openalex.org/) | 2.5 亿+ 篇论文，覆盖所有学科 | 开放，无需密钥 |
| [Semantic Scholar](https://www.semanticscholar.org/) | 2 亿+ 篇论文，侧重计算机科学和生物医学 | 建议申请免费 API 密钥 |
| [PubMed](https://pubmed.ncbi.nlm.nih.gov/) | 3600 万+ 条生物医学引文 | 建议申请免费 API 密钥 |
| [arXiv](https://arxiv.org/) | 200 万+ 篇 STEM 领域预印本 | 开放 |
| [BioRxiv](https://www.biorxiv.org/) | 生物学预印本 | 开放 |

通过 `--sources` 参数可以选择最适合你学科的组合。CS 方向推荐 `--sources s2,openalex,arxiv`。

## 测试

```bash
conda activate citebot
python -m pytest tests/ -v --cov=citebot --cov-report=term-missing
```

## 项目结构

```
CiteBot/
├── citebot/
│   ├── __init__.py              包初始化
│   ├── types.py                 不可变数据类型 + 异常层级
│   ├── config.py                配置管理（OpenCite + CLI 参数）
│   ├── latex_parser.py          .tex 文件解析
│   ├── keyword_extractor.py     LLM 优先关键词提取 + NLP 回退
│   ├── literature_searcher.py   异步多源搜索
│   ├── filter_ranker.py         去重 + 综合评分排序
│   ├── bib_generator.py         BibTeX 生成 + 校验
│   ├── cite_inserter.py         可选引用插入
│   ├── pipeline.py              流水线编排
│   └── main.py                  CLI 入口
├── tests/                       单元测试 + 集成测试
├── pyproject.toml               构建配置
├── requirements.txt             锁定的依赖版本
└── .env.example                 API 密钥模板
```

## 参与贡献

开源社区因学习、启发和创造而精彩，您的每一份贡献都**弥足珍贵**。

1. Fork 本项目
2. 创建特性分支（`git checkout -b feature/amazing-feature`）
3. 提交更改（`git commit -m 'feat: add amazing feature'`）
4. 推送分支（`git push origin feature/amazing-feature`）
5. 发起 Pull Request

## 许可证

基于 MIT License 发布。详见 [LICENSE](LICENSE)。

## 致谢

- [OpenCite](https://github.com/opencite/opencite) &mdash; 多源学术搜索引擎
- [KeyBERT](https://github.com/MaartenGr/KeyBERT) &mdash; 基于 BERT 的关键词提取
<p align="right"><a href="#readme-top">顶部</a></p>

<!-- MARKDOWN LINKS & IMAGES -->
[python-shield]: https://img.shields.io/badge/Python-3.11+-3776ab?style=for-the-badge&logo=python&logoColor=white
[python-url]: https://www.python.org/
[license-shield]: https://img.shields.io/badge/License-MIT-green?style=for-the-badge
[license-url]: https://opensource.org/licenses/MIT
[claude-shield]: https://img.shields.io/badge/Claude_Code-Powered-cc785c?style=for-the-badge&logo=anthropic&logoColor=white
[claude-url]: https://claude.ai/code
[opencite-shield]: https://img.shields.io/badge/OpenCite-Search-blue?style=for-the-badge
[opencite-url]: https://github.com/opencite/opencite
[deepseek-shield]: https://img.shields.io/badge/DeepSeek-LLM-4e6ef2?style=for-the-badge
[deepseek-url]: https://www.deepseek.com/
[click-shield]: https://img.shields.io/badge/Click-CLI-grey?style=for-the-badge
[click-url]: https://click.palletsprojects.com/
