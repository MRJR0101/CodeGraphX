"""
CodeGraphX 2.0 - Architectural Knowledge Graph (Phase 2)
Extracts structural backbone: packages, modules, files, classes, functions.
Resolves imports, calls, and inheritance relationships.
Computes fan_in, fan_out, instability metrics.
"""
import os
import ast as python_ast
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set

from codegraphx.core.models import (
    ASTNode, ArchNode, ArchRelationship, NodeLabel, RelationshipType,
    IngestionContext, generate_id,
)
from codegraphx.parsers.tree_sitter_parser import (
    collect_nodes_by_type, parse_repository, count_functions, count_classes,
    FUNCTION_TYPES, CLASS_TYPES,
)


# ── Extraction from AST ──────────────────────────────────────────────────────

class ArchitectureExtractor:
    """Builds the Architectural Knowledge Graph from parsed AST nodes."""

    def __init__(self):
        self.nodes: Dict[str, ArchNode] = {}
        self.relationships: List[ArchRelationship] = []
        self._name_to_id: Dict[str, str] = {}  # qualified_name -> node_id
        self._file_to_id: Dict[str, str] = {}  # file_path -> node_id

    def extract(self, ctx: IngestionContext) -> IngestionContext:
        """Run full architectural extraction from repository.

        Args:
            ctx: IngestionContext with repo_path set and ast_nodes populated.

        Returns:
            Updated IngestionContext with arch_nodes and arch_relationships.
        """
        repo_path = ctx.repo_path

        # 1. Create Repository node
        repo_node = self._create_node(
            NodeLabel.REPOSITORY,
            name=Path(repo_path).name,
            file_path=repo_path,
        )

        # 2. Walk directory structure → Packages, Modules, Files
        self._extract_file_structure(repo_path, repo_node.id)

        # 3. Extract classes and functions from each AST
        for ast_root in ctx.ast_nodes:
            self._extract_definitions(ast_root)

        # 4. Extract imports and resolve
        for ast_root in ctx.ast_nodes:
            self._extract_imports(ast_root, repo_path)

        # 5. Extract calls
        for ast_root in ctx.ast_nodes:
            self._extract_calls(ast_root)

        # 6. Extract inheritance
        for ast_root in ctx.ast_nodes:
            self._extract_inheritance(ast_root)

        # 7. Compute fan_in, fan_out, instability
        self._compute_metrics()

        # Pack results
        ctx.arch_nodes = list(self.nodes.values())
        ctx.arch_relationships = self.relationships

        return ctx

    # ── Node Creation ─────────────────────────────────────────────────────────

    def _create_node(self, label: NodeLabel, name: str,
                     file_path: str = "", module: str = "") -> ArchNode:
        """Create and register an ArchNode."""
        node = ArchNode(
            id=generate_id(),
            label=label,
            name=name,
            file_path=file_path,
            module=module,
        )
        self.nodes[node.id] = node
        qualified = f"{file_path}::{name}" if file_path else name
        self._name_to_id[qualified] = node.id
        self._name_to_id[name] = node.id
        if file_path:
            self._file_to_id[file_path] = node.id
        return node

    def _add_relationship(self, source_id: str, target_id: str,
                          rel_type: RelationshipType, **props):
        """Add a relationship between two nodes."""
        self.relationships.append(ArchRelationship(
            source_id=source_id,
            target_id=target_id,
            type=rel_type,
            properties=props,
        ))

    def _get_or_create_external(self, name: str) -> str:
        """Get or create an ExternalSymbol node."""
        key = f"external::{name}"
        if key in self._name_to_id:
            return self._name_to_id[key]
        node = ArchNode(
            id=generate_id(),
            label=NodeLabel.EXTERNAL_SYMBOL,
            name=name,
        )
        self.nodes[node.id] = node
        self._name_to_id[key] = node.id
        self._name_to_id[name] = node.id
        return node.id

    # ── File Structure ────────────────────────────────────────────────────────

    def _extract_file_structure(self, repo_path: str, repo_id: str):
        """Walk directory tree to create Package/Module/File nodes."""
        from codegraphx.core.config import config
        exclude = set(config.parser.exclude_dirs)
        supported_exts = set()
        for exts in config.parser.supported_extensions.values():
            supported_exts.update(exts)

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in exclude]

            rel_root = os.path.relpath(root, repo_path)

            # Directory → Package
            if rel_root == ".":
                parent_id = repo_id
            else:
                pkg_name = rel_root.replace(os.sep, ".")
                pkg_node = self._create_node(
                    NodeLabel.PACKAGE, name=pkg_name, file_path=root
                )
                # Link to repo
                self._add_relationship(repo_id, pkg_node.id, RelationshipType.CONTAINS)
                parent_id = pkg_node.id

            for fname in files:
                fpath = os.path.join(root, fname)
                ext = Path(fname).suffix.lower()
                if ext not in supported_exts:
                    continue

                # File → Module
                module_name = Path(fname).stem
                file_node = self._create_node(
                    NodeLabel.FILE, name=fname, file_path=fpath, module=module_name
                )
                module_node = self._create_node(
                    NodeLabel.MODULE, name=module_name, file_path=fpath, module=module_name
                )
                self._add_relationship(parent_id, file_node.id, RelationshipType.CONTAINS)
                self._add_relationship(file_node.id, module_node.id, RelationshipType.CONTAINS)

    # ── Definitions ───────────────────────────────────────────────────────────

    def _extract_definitions(self, ast_root: ASTNode):
        """Extract Class and Function definitions from AST."""
        file_path = ast_root.file_path
        file_id = self._file_to_id.get(file_path)

        # Functions
        functions = collect_nodes_by_type(ast_root, FUNCTION_TYPES)
        for func in functions:
            if func.name:
                func_node = self._create_node(
                    NodeLabel.FUNCTION, name=func.name, file_path=file_path,
                )
                func_node.properties["start_line"] = func.start_line
                func_node.properties["end_line"] = func.end_line
                func_node.properties["code"] = func.code[:500]
                if file_id:
                    self._add_relationship(file_id, func_node.id, RelationshipType.CONTAINS)

        # Classes
        classes = collect_nodes_by_type(ast_root, CLASS_TYPES)
        for cls in classes:
            if cls.name:
                cls_node = self._create_node(
                    NodeLabel.CLASS, name=cls.name, file_path=file_path,
                )
                cls_node.properties["start_line"] = cls.start_line
                cls_node.properties["end_line"] = cls.end_line
                if file_id:
                    self._add_relationship(file_id, cls_node.id, RelationshipType.CONTAINS)

    # ── Imports ───────────────────────────────────────────────────────────────

    def _extract_imports(self, ast_root: ASTNode, repo_path: str):
        """Extract import relationships. Resolve to internal or ExternalSymbol."""
        file_path = ast_root.file_path
        file_id = self._file_to_id.get(file_path)
        if not file_id:
            return

        import_nodes = collect_nodes_by_type(ast_root, {
            "import_statement", "import_from_statement",
        })

        for imp in import_nodes:
            imported_names = self._parse_import_text(imp.code)
            for imp_name in imported_names:
                # Try to resolve to internal module
                target_id = self._resolve_import(imp_name, repo_path)
                if target_id:
                    self._add_relationship(file_id, target_id, RelationshipType.IMPORTS)
                else:
                    ext_id = self._get_or_create_external(imp_name)
                    self._add_relationship(file_id, ext_id, RelationshipType.IMPORTS)

    def _parse_import_text(self, code: str) -> List[str]:
        """Parse import statement text to extract module names."""
        names = []
        # Python: import X or from X import Y
        match_from = re.match(r'from\s+([\w.]+)\s+import', code)
        if match_from:
            names.append(match_from.group(1))
            return names

        match_import = re.match(r'import\s+([\w.,\s]+)', code)
        if match_import:
            for part in match_import.group(1).split(","):
                name = part.strip().split(" as ")[0].strip()
                if name:
                    names.append(name)
            return names

        # JS: import ... from 'module'
        match_js = re.search(r"""(?:from|require\()\s*['"]([^'"]+)['"]""", code)
        if match_js:
            names.append(match_js.group(1))

        return names

    def _resolve_import(self, import_name: str, repo_path: str) -> Optional[str]:
        """Try to resolve import name to an internal module node ID."""
        # Check direct name match
        if import_name in self._name_to_id:
            return self._name_to_id[import_name]

        # Try as file path
        parts = import_name.replace(".", os.sep)
        candidates = [
            os.path.join(repo_path, parts + ".py"),
            os.path.join(repo_path, parts, "__init__.py"),
            os.path.join(repo_path, parts + ".js"),
        ]
        for candidate in candidates:
            if candidate in self._file_to_id:
                return self._file_to_id[candidate]

        return None

    # ── Calls ─────────────────────────────────────────────────────────────────

    def _extract_calls(self, ast_root: ASTNode):
        """Extract function call relationships."""
        file_path = ast_root.file_path
        call_nodes = collect_nodes_by_type(ast_root, {"call"})

        # Get functions defined in this file
        functions = collect_nodes_by_type(ast_root, FUNCTION_TYPES)
        func_names = {f.name for f in functions if f.name}

        for call in call_nodes:
            caller_func = self._find_enclosing_function(call, ast_root)
            if not caller_func or not caller_func.name:
                continue

            callee_name = self._extract_call_name(call.code)
            if not callee_name:
                continue

            caller_id = self._name_to_id.get(caller_func.name)
            if not caller_id:
                continue

            # Resolve callee
            callee_id = self._name_to_id.get(callee_name)
            if not callee_id:
                callee_id = self._get_or_create_external(callee_name)

            self._add_relationship(caller_id, callee_id, RelationshipType.CALLS)

    def _find_enclosing_function(self, node: ASTNode, root: ASTNode) -> Optional[ASTNode]:
        """Find the function that contains this node by line range."""
        functions = collect_nodes_by_type(root, FUNCTION_TYPES)
        best = None
        for func in functions:
            if func.start_line <= node.start_line <= node.end_line <= func.end_line:
                if best is None or (func.end_line - func.start_line) < (best.end_line - best.start_line):
                    best = func
        return best

    def _extract_call_name(self, code: str) -> Optional[str]:
        """Extract the called function name from call expression code."""
        # Match: func_name( or obj.method(
        match = re.match(r'([\w.]+)\s*\(', code.strip())
        if match:
            full = match.group(1)
            # Return just the last part for method calls
            parts = full.split(".")
            return parts[-1] if len(parts) > 1 else full
        return None

    # ── Inheritance ───────────────────────────────────────────────────────────

    def _extract_inheritance(self, ast_root: ASTNode):
        """Extract class inheritance relationships."""
        classes = collect_nodes_by_type(ast_root, CLASS_TYPES)

        for cls in classes:
            if not cls.name:
                continue

            cls_id = self._name_to_id.get(cls.name)
            if not cls_id:
                continue

            # Look for superclasses in the AST
            superclass_list = collect_nodes_by_type(cls, {"argument_list"})
            for arg_list in superclass_list:
                for child in arg_list.children:
                    if child.type == "identifier" and child.name:
                        parent_name = child.name
                        parent_id = self._name_to_id.get(parent_name)
                        if parent_id:
                            self._add_relationship(cls_id, parent_id, RelationshipType.INHERITS)
                        else:
                            ext_id = self._get_or_create_external(parent_name)
                            self._add_relationship(cls_id, ext_id, RelationshipType.INHERITS)

    # ── Metrics (Phase 2.4) ───────────────────────────────────────────────────

    def _compute_metrics(self):
        """Compute fan_in, fan_out, instability for all nodes."""
        # Count incoming and outgoing relationships per node
        incoming: Dict[str, int] = {}
        outgoing: Dict[str, int] = {}

        for rel in self.relationships:
            outgoing[rel.source_id] = outgoing.get(rel.source_id, 0) + 1
            incoming[rel.target_id] = incoming.get(rel.target_id, 0) + 1

        for node_id, node in self.nodes.items():
            node.fan_in = incoming.get(node_id, 0)
            node.fan_out = outgoing.get(node_id, 0)
            total = node.fan_in + node.fan_out
            node.instability = node.fan_out / total if total > 0 else 0.0


# ── Validation Queries (Phase 2.5) ───────────────────────────────────────────

class ArchitectureValidator:
    """Validation queries for the Architectural Knowledge Graph."""

    def __init__(self, extractor: ArchitectureExtractor):
        self.nodes = extractor.nodes
        self.relationships = extractor.relationships

    def find_circular_dependencies(self) -> List[List[str]]:
        """Detect circular dependency chains."""
        # Build adjacency list for DEPENDS_ON and IMPORTS
        adj: Dict[str, Set[str]] = {}
        for rel in self.relationships:
            if rel.type in (RelationshipType.DEPENDS_ON, RelationshipType.IMPORTS):
                adj.setdefault(rel.source_id, set()).add(rel.target_id)

        cycles = []
        visited = set()
        path = []
        path_set = set()

        def dfs(node_id: str):
            if node_id in path_set:
                cycle_start = path.index(node_id)
                cycle = [self.nodes[nid].name for nid in path[cycle_start:]]
                cycles.append(cycle)
                return
            if node_id in visited:
                return

            visited.add(node_id)
            path.append(node_id)
            path_set.add(node_id)

            for neighbor in adj.get(node_id, []):
                dfs(neighbor)

            path.pop()
            path_set.discard(node_id)

        for node_id in adj:
            dfs(node_id)

        return cycles

    def find_dead_modules(self) -> List[ArchNode]:
        """Find modules with no incoming edges."""
        has_incoming = set()
        for rel in self.relationships:
            has_incoming.add(rel.target_id)

        dead = []
        for node in self.nodes.values():
            if node.label == NodeLabel.MODULE and node.id not in has_incoming:
                dead.append(node)
        return dead

    def find_god_classes(self, threshold: int = 20) -> List[ArchNode]:
        """Find classes with fan_in + fan_out > threshold."""
        return [
            n for n in self.nodes.values()
            if n.label == NodeLabel.CLASS and (n.fan_in + n.fan_out) > threshold
        ]

    def find_dependency_hotspots(self, top_n: int = 10) -> List[Tuple[str, int]]:
        """Find nodes with highest total connections."""
        totals = [(n.name, n.fan_in + n.fan_out) for n in self.nodes.values()]
        totals.sort(key=lambda x: x[1], reverse=True)
        return totals[:top_n]
