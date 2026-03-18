# CiteBot

Intelligent LaTeX citation assistant. Reads `.tex` files (single or multi-file projects), extracts keywords via LLM or NLP, searches academic databases, and generates a `.bib` file with relevant references.

## Setup

```bash
conda activate citebot
pip install -e .
```

Copy `.env.example` to `.env` and fill in API keys. Key ones: `DEEPSEEK_API_KEY` (keyword extraction), `SEMANTIC_SCHOLAR_API_KEY` (search), `OPENCITE_EMAIL` (rate limits).

## Usage

```bash
# Single file
citebot paper.tex --num-refs 30 --output refs.bib
# Multi-file thesis (auto-tracks \input/\include)
citebot main.tex -n 100 -o refs.bib -k 50 --sources s2,openalex,arxiv
# With directory input
citebot thesis/ -n 100 -o refs.bib
# Insert citations into each chapter
citebot main.tex -n 100 -o refs.bib --insert-cites --verbose
```

## Architecture

Pipeline: `.tex` file(s) → parse project → keywords → search → rank → `.bib`

```
citebot/
├── types.py               Frozen dataclasses: TexDocument, TexProject, ScoredPaper, etc. + exceptions
├── config.py              CiteConfig wrapping OpenCite Config + CLI params
├── latex_parser.py        Regex-based .tex parsing with \input/\include resolution → TexProject
├── keyword_extractor.py   LLM-first (DeepSeek/OpenAI), chunked per-chapter for multi-file → NLP ensemble fallback
├── literature_searcher.py Async OpenCite SearchOrchestrator, query count scales with keyword count
├── filter_ranker.py       DOI + fuzzy title dedup, composite scoring (keyword/citation/recency/abstract)
├── bib_generator.py       fetch_bibtex → generate_bibtex fallback, bibtexparser validation
├── cite_inserter.py       \cite{} insertion into each file's .cited.tex (never overwrites original)
├── pipeline.py            Orchestrates flow, auto-detects multi-file, asyncio.run() bridges sync CLI → async
└── main.py                Click CLI entry point (accepts .tex file or directory)
```

## Key Patterns

- **Immutability**: All CiteBot data types are frozen dataclasses. Never mutate — use `dataclasses.replace()`.
- **Multi-file support**: `parse_tex_project()` recursively resolves `\input{}`/`\include{}`, searches `chapters/`, `sections/`, `content/`, `tex/` subdirs. `TexProject` aggregates main + child `TexDocument`s.
- **Async boundary**: `pipeline.run_pipeline()` calls `asyncio.run()` — only search and BibTeX fetch are async.
- **LLM+NLP fusion keywords**: LLM extracts domain-aware terms (weight 0.6), NLP ensemble extracts high-frequency terms (weight 0.4), shared terms get 1.5x boost. LLM prompt focuses on finding searchable related-work terms, not describing thesis contributions. Falls back to NLP-only if LLM unavailable.
- **Multi-file context engineering**: LLM generates project summary first, then per-chapter extraction with cumulative context (avoids duplicates). Multi-file chunked path uses LLM-only for performance.
- **Three-tier search queries**: Broad (unquoted short keywords), Medium (short + quoted phrase), Targeted (quoted phrases). Technical single-word terms allowed; generic words filtered via `_GENERIC_SINGLE_WORDS` set.
- **Scoring weights**: keyword_overlap 0.50, citation_score 0.15, recency_score 0.15, abstract_match 0.20.
- **Relevance filtering**: Papers need keyword_overlap ≥ 0.15 AND ≥ 2 distinct keyword matches (relaxed to 1 match when < 5 keywords).
- **Graceful degradation**: If LLM fails, fall back to NLP. If one search source fails, continue with remaining.
- **Multi-file cite insertion**: `insert_citations_project()` writes `.cited.tex` for all files, rewrites `\input`/`\include` paths in main file to point to `.cited` versions. Only main file gets bibliography commands.

## Testing

```bash
conda run -n citebot python -m pytest tests/ -v --cov=citebot
```

108 tests. Mock Paper objects in `tests/conftest.py`. Multi-file tests in `tests/test_multi_file.py`. Search query tests in `tests/test_literature_searcher.py`.

## Dependencies

- **Core**: opencite, bibtexparser, keybert, yake, spacy, rapidfuzz, click, rich, httpx
- **Models**: `en_core_web_sm` (spaCy), `all-MiniLM-L6-v2` (sentence-transformers via KeyBERT)
- **LLM**: DeepSeek API or any OpenAI-compatible API (for keyword extraction)
- **Environment**: conda env `citebot` (Python 3.11)

## Data Sources

Searched via OpenCite: OpenAlex, Semantic Scholar, PubMed, arXiv, BioRxiv. Configurable via `--sources`.
