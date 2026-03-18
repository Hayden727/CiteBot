<a id="readme-top"></a>

<!-- PROJECT LOGO -->
<div align="center">
  <img src="assets/profile.png" alt="CiteBot" width="400">
</div>

<br />

<!-- PROJECT SHIELDS -->
<div align="center">

[![Python][python-shield]][python-url]
[![License][license-shield]][license-url]
[![Claude Code][claude-shield]][claude-url]

</div>

<div align="center">

  <h3 align="center">CiteBot</h3>

  <p align="center">
    An intelligent citation assistant that analyzes your LaTeX document, searches academic databases, and generates a complete BibTeX file.
    <br />
    <br />
    <a href="https://github.com/Hayden727/CiteBot/issues/new?labels=bug">Report Bug</a>
    &middot;
    <a href="https://github.com/Hayden727/CiteBot/issues/new?labels=enhancement">Request Feature</a>
    &middot;
    <a href="README_zh.md">中文文档</a>
  </p>
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#about-the-project">About The Project</a></li>
    <li><a href="#features">Features</a></li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
        <li><a href="#configuration">Configuration</a></li>
      </ul>
    </li>
    <li>
      <a href="#usage">Usage</a>
      <ul>
        <li><a href="#basic-usage">Basic Usage</a></li>
        <li><a href="#advanced-options">Advanced Options</a></li>
        <li><a href="#all-options">All Options</a></li>
      </ul>
    </li>
    <li><a href="#how-it-works">How It Works</a></li>
    <li><a href="#data-sources">Data Sources</a></li>
    <li><a href="#testing">Testing</a></li>
    <li><a href="#repository-structure">Repository Structure</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

---

## About The Project

CiteBot automates the tedious process of finding and formatting references for academic papers. Give it your `.tex` file and a target number of references &mdash; it handles the rest: parsing your document, understanding what you're writing about, searching multiple academic databases in parallel, ranking results by relevance, and generating a ready-to-use `.bib` file.

### Built With

[![Python][python-shield]][python-url]
[![OpenCite][opencite-shield]][opencite-url]
[![DeepSeek][deepseek-shield]][deepseek-url]
[![Click][click-shield]][click-url]

## Features

- **LaTeX Parsing** &mdash; Extracts title, abstract, sections, and existing citations from `.tex` files (supports `\chapter`, `\section`, Chinese documents)
- **LLM-Powered Keyword Extraction** &mdash; Uses DeepSeek/OpenAI to understand document semantics and extract precise English academic terms; falls back to NLP ensemble (KeyBERT + YAKE + spaCy) when no LLM API is configured
- **Multi-Source Search** &mdash; Queries OpenAlex, Semantic Scholar, PubMed, arXiv, and BioRxiv in parallel via OpenCite
- **Smart Ranking** &mdash; Composite scoring: keyword overlap (40%), citation count (25%), recency (20%), abstract similarity (15%)
- **Deduplication** &mdash; DOI-based and fuzzy title matching to eliminate duplicates
- **BibTeX Generation** &mdash; Fetches authoritative BibTeX via DOI content negotiation with metadata fallback
- **Citation Insertion** &mdash; Optionally inserts `\cite{}` commands into your document (writes to `.cited.tex`, never overwrites the original)

## Getting Started

### Prerequisites

- [Anaconda](https://www.anaconda.com/) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- Python 3.11+

### Installation

```bash
conda create -n citebot python=3.11 -y
conda activate citebot

git clone https://github.com/Hayden727/CiteBot.git
cd CiteBot
pip install -e .
```

### Configuration

Copy the example environment file and fill in your API keys:

```bash
cp .env.example .env
```

| Variable | Purpose | Required |
|----------|---------|----------|
| `DEEPSEEK_API_KEY` | LLM keyword extraction (great for non-English docs) | Recommended |
| `OPENAI_API_KEY` | Alternative LLM (set `OPENAI_BASE_URL` + `OPENAI_MODEL` for compatible APIs) | Optional |
| `SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar API (free, recommended for CS) | Recommended |
| `OPENCITE_EMAIL` | OpenAlex polite pool (higher rate limits) | Recommended |
| `CROSSREF_EMAIL` | CrossRef polite pool | Optional |
| `PUBMED_API_KEY` | PubMed/NCBI access | Optional |

> CiteBot works without API keys, but keyword quality and search rate limits will be degraded.

## Usage

### Basic Usage

```bash
# Generate 30 references for your paper
citebot paper.tex --num-refs 30 --output references.bib

# Short flags
citebot paper.tex -n 30 -o refs.bib
```

### Advanced Options

```bash
# Insert \cite{} commands into the document
citebot paper.tex -n 50 -o refs.bib --insert-cites

# Filter by year range
citebot paper.tex --year-from 2020 --year-to 2025

# Select specific data sources (CS recommended)
citebot paper.tex --sources s2,openalex,arxiv

# Verbose output with reference table
citebot paper.tex -n 20 -o refs.bib -v
```

### All Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--num-refs` | `-n` | 30 | Number of references to find |
| `--output` | `-o` | `references.bib` | Output `.bib` file path |
| `--insert-cites` | | off | Insert `\cite{}` into `.tex` file |
| `--year-from` | | none | Minimum publication year |
| `--year-to` | | none | Maximum publication year |
| `--sources` | | all | Comma-separated: `openalex,s2,pubmed,arxiv,biorxiv` |
| `--keywords` | `-k` | 15 | Number of keywords to extract |
| `--verbose` | `-v` | off | Show detailed output |

## How It Works

```
┌──────────┐    ┌───────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Parse   │───>│  Extract  │───>│  Search  │───>│  Rank &  │───>│ Generate │
│  .tex    │    │ Keywords  │    │ Papers   │    │  Filter  │    │  .bib    │
└──────────┘    └───────────┘    └──────────┘    └──────────┘    └──────────┘
                                                                       │
                                                                       v
                                                                ┌──────────┐
                                                                │ (Insert  │
                                                                │  cites)  │
                                                                └──────────┘
```

1. **Parse** &mdash; Reads your `.tex` file and extracts the title, abstract, section structure, and plain text
2. **Extract Keywords** &mdash; Uses LLM (DeepSeek/OpenAI) for semantic keyword extraction, with NLP ensemble fallback (KeyBERT + YAKE + spaCy)
3. **Search** &mdash; Builds 3-5 queries of varying specificity and searches academic databases in parallel via OpenCite
4. **Rank & Filter** &mdash; Deduplicates results and scores each paper on keyword overlap (40%), citation count (25%), recency (20%), and abstract similarity (15%)
5. **Generate** &mdash; Fetches authoritative BibTeX entries via DOI, falling back to metadata-based generation
6. **Insert** (optional) &mdash; Adds `\cite{}` commands at relevant positions in a copy of your document

## Data Sources

| Source | Coverage | Access |
|--------|----------|--------|
| [OpenAlex](https://openalex.org/) | 250M+ works across all disciplines | Open, no key required |
| [Semantic Scholar](https://www.semanticscholar.org/) | 200M+ papers, CS/biomedical focus | Free API key recommended |
| [PubMed](https://pubmed.ncbi.nlm.nih.gov/) | 36M+ biomedical citations | Free API key recommended |
| [arXiv](https://arxiv.org/) | 2M+ preprints in STEM fields | Open |
| [BioRxiv](https://www.biorxiv.org/) | Biology preprints | Open |

Configurable via `--sources`. For CS papers, `--sources s2,openalex,arxiv` is recommended.

## Testing

```bash
conda activate citebot
python -m pytest tests/ -v --cov=citebot --cov-report=term-missing
```

## Repository Structure

```
CiteBot/
├── citebot/
│   ├── __init__.py              Package init
│   ├── types.py                 Frozen dataclasses + exception hierarchy
│   ├── config.py                Configuration (OpenCite + CLI params)
│   ├── latex_parser.py          .tex file parsing
│   ├── keyword_extractor.py     LLM-first keyword extraction + NLP fallback
│   ├── literature_searcher.py   Async multi-source search
│   ├── filter_ranker.py         Deduplication + composite scoring
│   ├── bib_generator.py         BibTeX generation + validation
│   ├── cite_inserter.py         Optional \cite{} insertion
│   ├── pipeline.py              Pipeline orchestration
│   └── main.py                  CLI entry point
├── tests/                       Unit + integration tests
├── pyproject.toml               Build configuration
├── requirements.txt             Pinned dependencies
└── .env.example                 API key template
```

## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/amazing-feature`)
3. Commit your Changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the Branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

## Acknowledgments

- [OpenCite](https://github.com/opencite/opencite) &mdash; Multi-source academic search engine
- [KeyBERT](https://github.com/MaartenGr/KeyBERT) &mdash; Keyword extraction with BERT embeddings
<p align="right"><a href="#readme-top">TOP</a></p>

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
