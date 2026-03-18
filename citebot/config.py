"""CiteBot configuration — wraps OpenCite Config with CLI parameters."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from opencite.config import Config as OpenCiteConfig

logger = logging.getLogger(__name__)

ALL_SOURCES: tuple[str, ...] = ("openalex", "s2", "pubmed", "arxiv", "biorxiv")


@dataclass(frozen=True)
class CiteConfig:
    """Immutable configuration for a CiteBot run."""

    opencite_config: OpenCiteConfig
    num_refs: int = 30
    output_path: str = "references.bib"
    insert_cites: bool = False
    year_from: int | None = None
    year_to: int | None = None
    sources: tuple[str, ...] = ALL_SOURCES
    keyword_top_n: int = 15
    crossref_email: str = ""
    log_level: str = "WARNING"


def build_config(
    *,
    num_refs: int = 30,
    output: str = "references.bib",
    insert_cites: bool = False,
    year_from: int | None = None,
    year_to: int | None = None,
    sources: tuple[str, ...] | None = None,
    keyword_top_n: int = 15,
    verbose: bool = False,
) -> CiteConfig:
    """Build a CiteConfig from CLI args and environment variables.

    OpenCite's Config is loaded from its own chain:
      env vars > .env > ~/.opencite/config.toml > defaults

    CiteBot-specific env vars:
      CROSSREF_EMAIL  — for CrossRef polite pool
      CITEBOT_LOG_LEVEL — override log level
    """
    opencite_cfg = OpenCiteConfig.from_env()

    log_level = os.environ.get("CITEBOT_LOG_LEVEL", "DEBUG" if verbose else "WARNING")
    crossref_email = os.environ.get("CROSSREF_EMAIL", "")

    resolved_sources = sources if sources is not None else ALL_SOURCES
    for src in resolved_sources:
        if src not in ALL_SOURCES:
            raise ValueError(
                f"Unknown source '{src}'. Choose from: {', '.join(ALL_SOURCES)}"
            )

    config = CiteConfig(
        opencite_config=opencite_cfg,
        num_refs=num_refs,
        output_path=output,
        insert_cites=insert_cites,
        year_from=year_from,
        year_to=year_to,
        sources=resolved_sources,
        keyword_top_n=keyword_top_n,
        crossref_email=crossref_email,
        log_level=log_level,
    )

    logging.basicConfig(level=getattr(logging, config.log_level, logging.WARNING))
    logger.debug("CiteConfig built: num_refs=%d, sources=%s", num_refs, resolved_sources)

    return config
