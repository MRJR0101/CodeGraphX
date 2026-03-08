"""Language parsers for codegraphx.

Public API:
    parse_python(file_text) -> ParseResult
    parse_js(ext, file_text) -> ParseResult

ParseResult = tuple[functions, imports, calls, function_calls, line_count]
"""

from codegraphx.core.parsers.javascript import parse_js
from codegraphx.core.parsers.python import parse_python

__all__ = ["parse_js", "parse_python"]
