"""Pipeline orchestration — ties all CiteBot modules together."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from citebot.bib_generator import generate_bibtex_content, write_bib_file
from citebot.cite_inserter import insert_citations_project
from citebot.config import CiteConfig
from citebot.filter_ranker import filter_and_rank
from citebot.keyword_extractor import extract_keywords, extract_keywords_from_project
from citebot.latex_parser import parse_tex_file, parse_tex_project
from citebot.literature_searcher import search_papers
from citebot.types import PipelineResult, TexProject

logger = logging.getLogger(__name__)
console = Console()


def run_pipeline(tex_path: str, config: CiteConfig) -> PipelineResult:
    """Synchronous entry point — bridges to async pipeline via asyncio.run()."""
    return asyncio.run(_run_pipeline_async(tex_path, config))


async def _run_pipeline_async(tex_path: str, config: CiteConfig) -> PipelineResult:
    """Execute the full CiteBot pipeline.

    Automatically detects multi-file projects via \\input/\\include.

    Steps:
        1. Parse .tex file(s) into TexProject
        2. Extract keywords (LLM chunked for multi-file)
        3. Search literature (async network)
        4. Filter and rank (sync)
        5. Generate BibTeX (async network)
        6. Optionally insert citations into each file
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        # Step 1: Parse
        task = progress.add_task("Parsing .tex file(s)...", total=None)
        project = parse_tex_project(tex_path)

        if project.is_multi_file:
            file_count = len(project.all_docs)
            progress.update(
                task,
                description=f"[green]Parsed {file_count} files ({project.combined_title[:40]})",
            )
        else:
            progress.update(task, description="[green]Parsed .tex file")

        # Step 2: Keywords
        progress.update(task, description="Extracting keywords...")
        if project.is_multi_file:
            keywords = extract_keywords_from_project(project, top_n=config.keyword_top_n)
        else:
            keywords = extract_keywords(project.main_doc, top_n=config.keyword_top_n)
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

        # Step 4: Rank — use a virtual TexDocument with combined text for scoring
        progress.update(task, description="Ranking and filtering...")
        from citebot.types import TexDocument as _TD
        combined_doc = _TD(
            file_path=project.main_doc.file_path,
            title=project.combined_title,
            abstract=project.combined_abstract,
            sections=(),
            full_text=project.combined_full_text,
            existing_cite_keys=project.all_existing_cite_keys,
            existing_bib_file=project.bib_file,
        )
        scored = filter_and_rank(raw_papers, keywords, combined_doc, config.num_refs)
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
            written = insert_citations_project(project, scored, bib_filename=bib_name)
            inserted = len(written) > 0
            progress.update(
                task,
                description=f"[green]Citations inserted into {len(written)} file(s)",
            )

        progress.update(task, description="[green]Done!")

    return PipelineResult(
        project=project,
        keywords=keywords,
        papers=scored,
        bibtex_content=bibtex_content,
        output_path=output_path,
        inserted_cites=inserted,
    )
