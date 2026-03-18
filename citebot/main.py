"""CiteBot CLI entry point."""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.table import Table

from pathlib import Path

from citebot.config import build_config
from citebot.pipeline import run_pipeline
from citebot.types import CiteBotError, SearchError, TexParseError

console = Console()


@click.command()
@click.argument("tex_file", type=click.Path(exists=True))
@click.option(
    "--num-refs", "-n", default=30, show_default=True,
    help="Number of references to find.",
)
@click.option(
    "--output", "-o", default="references.bib", show_default=True,
    help="Output .bib file path.",
)
@click.option(
    "--insert-cites", is_flag=True, default=False,
    help="Insert \\cite{} commands into the .tex file.",
)
@click.option(
    "--year-from", type=int, default=None,
    help="Minimum publication year filter.",
)
@click.option(
    "--year-to", type=int, default=None,
    help="Maximum publication year filter.",
)
@click.option(
    "--sources", default=None,
    help="Comma-separated data sources: openalex,s2,pubmed,arxiv,biorxiv",
)
@click.option(
    "--keywords", "-k", default=15, show_default=True,
    help="Number of keywords to extract.",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output.")
def main(
    tex_file: str,
    num_refs: int,
    output: str,
    insert_cites: bool,
    year_from: int | None,
    year_to: int | None,
    sources: str | None,
    keywords: int,
    verbose: bool,
) -> None:
    """CiteBot: Intelligent LaTeX citation assistant.

    Reads a .tex file (auto-tracking \\input/\\include for multi-file projects),
    extracts keywords, searches academic databases, and generates a .bib file.

    \b
    Examples:
        citebot paper.tex --num-refs 30 --output refs.bib
        citebot main.tex -n 100 -o refs.bib --sources s2,openalex,arxiv
    """
    # Resolve directory input to main .tex file
    resolved_tex = _resolve_input(tex_file)

    parsed_sources = (
        tuple(s.strip() for s in sources.split(",") if s.strip())
        if sources
        else None
    )

    try:
        config = build_config(
            num_refs=num_refs,
            output=output,
            insert_cites=insert_cites,
            year_from=year_from,
            year_to=year_to,
            sources=parsed_sources,
            keyword_top_n=keywords,
            verbose=verbose,
        )

        result = run_pipeline(resolved_tex, config)
        _print_summary(result, verbose)

    except TexParseError as exc:
        console.print(f"[red]Parse error:[/red] {exc}")
        sys.exit(1)
    except SearchError as exc:
        console.print(f"[yellow]Search warning:[/yellow] {exc}")
        sys.exit(1)
    except CiteBotError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(130)


def _print_summary(result, verbose: bool) -> None:
    """Print a formatted summary of the pipeline result."""
    console.print()
    console.print("[bold green]CiteBot complete![/bold green]")
    console.print()

    # Project info
    project = result.project
    if project.is_multi_file:
        console.print(f"[bold]Project:[/bold] {len(project.all_docs)} files parsed")

    # Keywords
    kw_display = ", ".join(kw for kw, _ in result.keywords.keywords[:8])
    console.print(f"[bold]Keywords:[/bold] {kw_display}")
    if len(result.keywords.keywords) > 8:
        console.print(f"[dim]  ... and {len(result.keywords.keywords) - 8} more[/dim]")
    console.print(f"[bold]Papers found:[/bold] {len(result.papers)}")
    console.print(f"[bold]BibTeX file:[/bold] {result.output_path}")

    if result.inserted_cites:
        n_files = len(project.all_docs) if project.is_multi_file else 1
        console.print(f"[bold]Citations:[/bold] Inserted into {n_files} .cited.tex file(s)")

    if verbose and result.papers:
        console.print()
        table = Table(title="Top References")
        table.add_column("#", style="dim", width=3)
        table.add_column("Cite Key", style="cyan")
        table.add_column("Title", max_width=50)
        table.add_column("Year", justify="center")
        table.add_column("Score", justify="right")

        for i, sp in enumerate(result.papers[:15], 1):
            title = (sp.paper.title or "")[:50]
            year = str(sp.paper.year) if sp.paper.year else "?"
            table.add_row(
                str(i), sp.cite_key, title, year, f"{sp.relevance_score:.3f}"
            )

        console.print(table)


def _resolve_input(tex_file: str) -> str:
    """Resolve input path: if directory, find the main .tex file inside it."""
    path = Path(tex_file)

    if path.is_file():
        return str(path)

    if path.is_dir():
        # Look for common main file names
        for name in ("main.tex", "thesis.tex", "paper.tex", "document.tex"):
            candidate = path / name
            if candidate.is_file():
                console.print(f"[dim]Found main file: {candidate}[/dim]")
                return str(candidate)

        # Fall back to any .tex file containing \documentclass
        for tex in sorted(path.glob("*.tex")):
            content = tex.read_text(encoding="utf-8", errors="ignore")[:2000]
            if r"\documentclass" in content:
                console.print(f"[dim]Found main file: {tex}[/dim]")
                return str(tex)

        # Last resort: first .tex file
        tex_files = sorted(path.glob("*.tex"))
        if tex_files:
            console.print(f"[dim]Using first .tex file: {tex_files[0]}[/dim]")
            return str(tex_files[0])

        console.print(f"[red]No .tex files found in {path}[/red]")
        raise SystemExit(1)

    console.print(f"[red]Path not found: {path}[/red]")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
