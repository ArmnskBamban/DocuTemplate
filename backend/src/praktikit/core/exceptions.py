"""Domain exception hierarchy.

Exceptions carry clear, user-facing messages. The CLI/API layers translate
these into appropriate responses. We never expose raw ``500`` errors without an
explanation (spec Section 44).
"""

from __future__ import annotations


class PraktikitError(Exception):
    """Base class for all PraktiKit errors."""


class UnsupportedFormatError(PraktikitError):
    """The uploaded file format is not supported (e.g. legacy ``.doc`` or PDF)."""


class DocxValidationError(PraktikitError):
    """The file is not a valid, trustworthy DOCX package (spec Section 10)."""


class ParseError(PraktikitError):
    """The DOCX could not be parsed (corrupt XML, missing parts, unexpected structure)."""


class GenerationError(PraktikitError):
    """Template generation failed before producing an output file."""


class ValidationFailedError(PraktikitError):
    """The generated output failed post-generation validation (spec Section 43)."""


class LeakDetectedError(PraktikitError):
    """Potential old report content was detected in the generated output (spec Section 42).

    Raised in strict mode when the leak detector finds shared long content
    between the source body and the generated template.
    """


class UnsafeContentError(PraktikitError):
    """The document contains unsafe constructs (zip traversal, external entities, macros)."""
