"""PraktiKit — Smart Report Template Extractor.

Turns a finished practicum report (.docx) into a clean, reusable template by
preserving structure and formatting while removing the previous report's
specific content and replacing identity fields with placeholders.

The core engine is fully deterministic and works without any LLM. See the
package README and ``docs/`` for architecture details.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
