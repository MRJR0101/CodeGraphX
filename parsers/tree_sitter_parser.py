"""
CodeGraphX 2.0 - Core Parsing Engine (Phase 1)
Deterministic AST extraction across languages using tree-sitter.

Phase 1 Rules:
- Store AST in memory only. No Neo4j writes.
- Each parsed node includes: id, type, name, code, file_path, start_line, end_line
"""
import os
from pathlib import Path
from typing import List, Optional, Dict, Tuple

from tree_sitter import Language, Parser, Node
import tree_sitter_python as tsp
import tree_sitter_javascript as tsjs

from codegraphx.core.models import ASTNode, Language as LangEnum, generate_id
from codegraphx.core.config import config


# ── Language Registry ─────────────────────────────────────────────────────────

LANGUAGE_MAP: Dict[str, Language] = {
    "python": Language(tsp.language()),
    "javascript": Language(tsjs.language()),
}

EXTENSION_MAP: Dict[str, str] = {}
for lang, exts in config.parser.supported_extensions.items():
    for ext in exts:
        EXTENSION_MAP[ext] = lang


# ── Node types that carry names ──────────────────────────────────────────────

NAMED_NODE_TYPES = {
    # Python
    "function_definition", "class_definition", "decorated_definition",
    "import_statement", "import_from_statement",
    # JavaScript
    "function_declaration", "class_declaration", "method_definition",
    "arrow_function", "variable_declarator",
    "import_statement", "export_statement",
}

FUNCTION_TYPES = {
    "function_definition", "function_declaration", "method_definition",
    "arrow_function",
}

CLASS_TYPES = {
    "class_definition", "class_declaration",
}


# ── Name Extraction ──────────────────────────────────────────────────────────

def extract_name(node: Node, source: bytes) -> Optional[str]:
    """Extract the identifier name from a tree-sitter node."""
    # Look for direct 'name' field
    name_node = node.child_by_field_name("name")
    if name_node:
        return source[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")

    # For decorated definitions, look inside
    if node.type == "decorated_definition":
        for child in node.children:
            if child.type in ("function_definition", "class_definition"):
                return extract_name(child, source)

    # For variable declarators (JS), get the name child
    if node.type == "variable_declarator":
        name_node = node.child_by_field_name("name")
        if name_node:
            return source[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")

    # For imports, return the full import text
    if node.type in ("import_statement", "import_from_statement"):
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace").strip()

    return None


# ── AST Walker ────────────────────────────────────────────────────────────────

def walk_tree(node: Node, source: bytes, file_path: str,
              language: str, depth: int = 0) -> ASTNode:
    """Recursively walk a tree-sitter tree and produce ASTNode objects."""
    code_text = source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    ast_node = ASTNode(
        id=generate_id(),
        type=node.type,
        name=extract_name(node, source),
        code=code_text if len(code_text) <= 2000 else code_text[:2000] + "...",
        file_path=file_path,
        start_line=node.start_point[0] + 1,  # 1-indexed
        end_line=node.end_point[0] + 1,
        language=language,
        children=[],
    )

    for child in node.children:
        child_ast = walk_tree(child, source, file_path, language, depth + 1)
        ast_node.children.append(child_ast)

    return ast_node


# ── File Parser ───────────────────────────────────────────────────────────────

def parse_file(file_path: str, language: Optional[str] = None) -> Optional[ASTNode]:
    """Parse a single source file into an AST tree.

    Args:
        file_path: Path to the source file.
        language: Override language detection.

    Returns:
        Root ASTNode or None if parsing fails.
    """
    path = Path(file_path)

    if not path.exists():
        return None

    # Determine language
    if language is None:
        ext = path.suffix.lower()
        language = EXTENSION_MAP.get(ext)
        if language is None:
            return None

    if language not in LANGUAGE_MAP:
        return None

    # Size check
    file_size_kb = path.stat().st_size / 1024
    if file_size_kb > config.parser.max_file_size_kb:
        return None

    # Read source
    try:
        source = path.read_bytes()
    except (IOError, OSError):
        return None

    # Parse
    ts_language = LANGUAGE_MAP[language]
    parser = Parser(ts_language)
    tree = parser.parse(source)

    if tree.root_node is None:
        return None

    return walk_tree(tree.root_node, source, str(path), language)


# ── Repository Parser ─────────────────────────────────────────────────────────

def parse_repository(repo_path: str) -> List[ASTNode]:
    """Parse all supported files in a repository.

    Returns:
        List of root ASTNode objects, one per file.
    """
    repo = Path(repo_path)
    if not repo.is_dir():
        raise ValueError(f"Repository path does not exist: {repo_path}")

    results: List[ASTNode] = []
    exclude = set(config.parser.exclude_dirs)

    for root, dirs, files in os.walk(repo):
        # Prune excluded directories
        dirs[:] = [d for d in dirs if d not in exclude]

        for fname in files:
            fpath = os.path.join(root, fname)
            ext = Path(fname).suffix.lower()

            if ext not in EXTENSION_MAP:
                continue

            ast = parse_file(fpath)
            if ast is not None:
                results.append(ast)

    return results


# ── Statistics ────────────────────────────────────────────────────────────────

def count_functions(ast_root: ASTNode) -> int:
    """Count all function definitions in an AST tree."""
    count = 1 if ast_root.type in FUNCTION_TYPES else 0
    for child in ast_root.children:
        count += count_functions(child)
    return count


def count_classes(ast_root: ASTNode) -> int:
    """Count all class definitions in an AST tree."""
    count = 1 if ast_root.type in CLASS_TYPES else 0
    for child in ast_root.children:
        count += count_classes(child)
    return count


def collect_nodes_by_type(ast_root: ASTNode, node_types: set) -> List[ASTNode]:
    """Collect all nodes matching given types from the AST tree."""
    results = []
    if ast_root.type in node_types:
        results.append(ast_root)
    for child in ast_root.children:
        results.extend(collect_nodes_by_type(child, node_types))
    return results


def flatten_ast(ast_root: ASTNode) -> List[ASTNode]:
    """Flatten AST tree into a list of all nodes."""
    results = [ast_root]
    for child in ast_root.children:
        results.extend(flatten_ast(child))
    return results
