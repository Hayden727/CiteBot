# CiteBot

An intelligent citation assistant that automatically analyzes your LaTeX document, searches academic databases, and generates a complete BibTeX file with relevant references.

## Features

- **LaTeX Parsing** — Extracts title, abstract, sections, and existing citations from `.tex` files
- **LLM-Powered Keyword Extraction** — Uses DeepSeek/OpenAI to understand document semantics and extract precise English academic terms; falls back to NLP ensemble (KeyBERT + YAKE + spaCy) when no LLM API is configured. Handles Chinese and other non-English documents natively
- **Multi-Source Search** — Queries OpenAlex, Semantic Scholar, PubMed, arXiv, and BioRxiv in parallel
- **Smart Ranking** — Composite scoring based on keyword overlap, citation count, recency, and abstract similarity
- **Deduplication** — DOI-based and fuzzy title matching to eliminate duplicate results
- **BibTeX Generation** — Fetches authoritative BibTeX via DOI content negotiation with metadata fallback
- **Citation Insertion** — Optionally inserts `\cite{}` commands into your document (writes to `.cited.tex`, never overwrites the original)

## Quick Start

### Prerequisites

- [Anaconda](https://www.anaconda.com/) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- Python 3.11+

### Installation

```bash
# Create and activate the conda environment
conda create -n citebot python=3.11 -y
conda activate citebot

# Install CiteBot
git clone <repo-url> && cd CiteBot
pip install -e .
```

### Configuration (optional but recommended)

Copy the example environment file and fill in your API keys for higher rate limits:

```bash
cp .env.example .env
```

Available keys:

| Variable | Purpose |
|----------|---------|
| `DEEPSEEK_API_KEY` | **Recommended** — LLM keyword extraction (great for non-English docs) |
| `OPENAI_API_KEY` | Alternative LLM provider (set `OPENAI_BASE_URL` and `OPENAI_MODEL` for compatible APIs) |
| `SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar API access (free, recommended for CS) |
| `OPENCITE_EMAIL` | Contact email for OpenAlex polite pool (higher rate limits) |
| `CROSSREF_EMAIL` | CrossRef polite pool |
| `PUBMED_API_KEY` | PubMed/NCBI access |

CiteBot works without API keys, but keyword quality and search rate limits will be degraded.

## Usage

### Basic

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

# Select specific data sources
citebot paper.tex --sources openalex,s2,arxiv

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

1. **Parse** — Reads your `.tex` file and extracts the title, abstract, section structure, and plain text
2. **Extract Keywords** — Uses LLM (DeepSeek/OpenAI) for semantic keyword extraction, with NLP ensemble fallback (KeyBERT + YAKE + spaCy)
3. **Search** — Builds 3-5 queries of varying specificity and searches academic databases in parallel via OpenCite
4. **Rank & Filter** — Deduplicates results and scores each paper on keyword overlap (40%), citation count (25%), recency (20%), and abstract similarity (15%)
5. **Generate** — Fetches authoritative BibTeX entries via DOI, falling back to metadata-based generation
6. **Insert** (optional) — Adds `\cite{}` commands at relevant positions in a copy of your document

## Project Structure

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
├── tests/                       72 unit + integration tests
├── pyproject.toml               Build configuration
├── requirements.txt             Pinned dependencies
└── .env.example                 API key template
```

## Development

### Run Tests

```bash
conda activate citebot
python -m pytest tests/ -v --cov=citebot --cov-report=term-missing
```

### Data Sources

| Source | Coverage | Access |
|--------|----------|--------|
| [OpenAlex](https://openalex.org/) | 250M+ works across all disciplines | Open, no key required |
| [Semantic Scholar](https://www.semanticscholar.org/) | 200M+ papers, CS/biomedical focus | Free API key recommended |
| [PubMed](https://pubmed.ncbi.nlm.nih.gov/) | 36M+ biomedical citations | Free API key recommended |
| [arXiv](https://arxiv.org/) | 2M+ preprints in STEM fields | Open |
| [BioRxiv](https://www.biorxiv.org/) | Biology preprints | Open |

## License

MIT
