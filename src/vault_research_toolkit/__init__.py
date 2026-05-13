"""vault-research-toolkit: vault-based research primitives for Fin Studio.

Public surface:

    from vault_research_toolkit import frontmatter, panel
    from vault_research_toolkit.panel import write_panel, read_panel, df_to_md
"""

from __future__ import annotations

from . import frontmatter, panel

__version__ = "0.2.0"

__all__ = [
    "frontmatter",
    "panel",
    "__version__",
]
