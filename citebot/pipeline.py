"""Pipeline orchestration — ties all CiteBot modules together."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from citebot.bib_generator import generate_bibtex_content, write_bib_file
from citebot.cite_inserter import insert_citations, write_modified_tex
from citebot.config import CiteConfig
from citebot.filter_ranker import filter_and_rank
from citebot.keyword_extractor import extract_keywords
from citebot.latex_parser import parse_tex_file
from citebot.literature_searcher import search_papers
from citebot.types import PipelineResult

logger = logging.getLogger(__name__)
console = Console()


def run_pipeline(tex_path: str, config: CiteConfig) -> PipelineResult:
    """Synchronous entry point — bridges to async pipeline via asyncio.run()."""
    return asyncio.run(_run_pipeline_async(tex_path, config))


async def _run_pipeline_async(tex_path: str, config: CiteConfig) -> PipelineResult:
    """Execute the full CiteBot pipeline.

    Steps:
        1. Parse .tex file
        2. Extract keywords (sync NLP)
        3. Search literature (async network)
        4. Filter and rank (sync)
        5. Generate BibTeX (async network)
        6. Optionally insert citations (sync)
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        # Step 1: Parse
        task = progress.add_task("Parsing .tex file...", total=None)
        document = parse_tex_file(tex_path)
        progress.update(task, description="[green]Parsed .tex file")

        # Step 2: Keywords
        progress.update(task, description="Extracting keywords...")
        keywords = extract_keywords(document, top_n=config.keyword_top_n)
        progress.update(
            task,
            description=f"[green]Extracted {len(keywords.keywords)} keywords",
        )

        # Step 3: Search
        progress.update(
            task,
            description=f"Searching {len(config.sources)} databases...",
        )
        raw_papers = await search_papers(keywords, config)
        progress.update(
            task,
            description=f"[green]Found {len(raw_papers)} raw results",
        )

        # Step 4: Rank
        progress.update(task, description="Ranking and filtering...")
        scored = filter_and_rank(raw_papers, keywords, document, config.num_refs)
        progress.update(
            task,
            description=f"[green]Selected top {len(scored)} papers",
        )

        # Step 5: Generate BibTeX
        progress.update(task, description="Generating BibTeX entries...")
        bibtex_content = await generate_bibtex_content(scored)
        output_path = write_bib_file(bibtex_content, config.output_path)
        progress.update(
            task,
            description=f"[green]Wrote {output_path}",
        )

        # Step 6: Optional cite insertion
        inserted = False
        if config.insert_cites:
            progress.update(task, description="Inserting citations...")
            bib_name = Path(config.output_path).stem
            modified_tex = insert_citations(document, scored, bib_filename=bib_name)
            write_modified_tex(modified_tex, document.file_path)
            inserted = True
            progress.update(task, description="[green]Citations inserted")

        progress.update(task, description="[green]Done!")

    return PipelineResult(
        document=document,
        keywords=keywords,
        papers=scored,
        bibtex_content=bibtex_content,
        output_path=output_path,
        inserted_cites=inserted,
    )
