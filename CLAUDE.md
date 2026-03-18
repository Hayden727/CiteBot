# CiteBot

Intelligent LaTeX citation assistant. Reads a `.tex` file, extracts keywords via LLM or NLP, searches academic databases, and generates a `.bib` file with relevant references.

## Setup

```bash
conda activate citebot
pip install -e .
```

Copy `.env.example` to `.env` and fill in API keys. Key ones: `DEEPSEEK_API_KEY` (keyword extraction), `SEMANTIC_SCHOLAR_API_KEY` (search), `OPENCITE_EMAIL` (rate limits).

## Usage

```bash
citebot paper.tex --num-refs 30 --output refs.bib
citebot paper.tex -n 50 -o refs.bib --insert-cites --verbose
citebot paper.tex --sources s2,openalex,arxiv --year-from 2020
```

## Architecture

Pipeline: `.tex` → parse → keywords → search → rank → `.bib`

```
citebot/
├── types.py               Frozen dataclasses (TexDocument, ScoredPaper, etc.) + exceptions
├── config.py              CiteConfig wrapping OpenCite Config + CLI params
├── latex_parser.py        Regex-based .tex parsing → TexDocument (handles \chapter, tables, figures, Chinese)
├── keyword_extractor.py   LLM-first (DeepSeek/OpenAI) → NLP ensemble fallback (KeyBERT+YAKE+spaCy)
├── literature_searcher.py Async OpenCite SearchOrchestrator, multi-query strategy
├── filter_ranker.py       DOI + fuzzy title dedup, composite scoring (keyword/citation/recency/abstract)
├── bib_generator.py       fetch_bibtex → generate_bibtex fallback, bibtexparser validation
├── cite_inserter.py       Optional \cite{} insertion into .cited.tex (never overwrites original)
├── pipeline.py            Orchestrates flow, asyncio.run() bridges sync CLI → async search
└── main.py                Click CLI entry point
```

## Key Patterns

- **Immutability**: All CiteBot data types are frozen dataclasses. Never mutate — use `dataclasses.replace()`.
- **Async boundary**: `pipeline.run_pipeline()` calls `asyncio.run()` — only search and BibTeX fetch are async.
- **LLM-first keywords**: Calls DeepSeek/OpenAI API via httpx to extract English academic terms from any language doc. Falls back to NLP ensemble (KeyBERT 0.5 + YAKE 0.3 + spaCy 0.2) when no LLM API configured. Config resolved from env: `DEEPSEEK_API_KEY` or `OPENAI_API_KEY`+`OPENAI_BASE_URL`+`OPENAI_MODEL`.
- **Scoring weights**: keyword_overlap 0.40, citation_score 0.25, recency_score 0.20, abstract_match 0.15.
- **Graceful degradation**: If LLM fails, fall back to NLP. If one search source fails, continue with remaining.
- **OpenCite**: `SearchOrchestrator` for multi-source search (openalex, s2, pubmed, arxiv, biorxiv), `fetch_bibtex` for BibTeX.

## Testing

```bash
conda run -n citebot python -m pytest tests/ -v --cov=citebot
```

Target: 80%+ coverage. Tests use mock Paper objects defined in `tests/conftest.py`.

## Dependencies

- **Core**: opencite, bibtexparser, keybert, yake, spacy, rapidfuzz, click, rich, httpx
- **Models**: `en_core_web_sm` (spaCy), `all-MiniLM-L6-v2` (sentence-transformers via KeyBERT)
- **LLM**: DeepSeek API or any OpenAI-compatible API (for keyword extraction)
- **Environment**: conda env `citebot` (Python 3.11)

## Data Sources

Searched via OpenCite: OpenAlex, Semantic Scholar, PubMed, arXiv, BioRxiv. Configurable via `--sources`.
