"""vault-research-toolkit: vault-based research primitives.

Public surface:

    from vault_research_toolkit import frontmatter, sections
    from vault_research_toolkit.research import ResearchSkillSpec, main, run_refresh
"""

from __future__ import annotations

from . import frontmatter, sections
from .research import ResearchSkillSpec, main, run_refresh

__version__ = "0.1.0"

__all__ = [
    "frontmatter",
    "sections",
    "ResearchSkillSpec",
    "main",
    "run_refresh",
    "__version__",
]
