"""Tracked files merge-gate Python files import, or run by a `.py` literal, to a fixpoint (#401).

Literals in `tests/` are expectations (the freshness pin's), not runs.
"""

import ast
import posixpath

# The `sys.path` entries the tree adds beside a file's own directory.
SEARCH_ROOTS = ("", "scripts", "scripts/ci")


def module_files(name, bases, tracked):
    found = set()
    parts = name.split(".") if name else []
    for base in bases:
        for depth in range(1, len(parts) + 1):
            stem = posixpath.join(base, *parts[:depth])
            found.update({stem + ".py", stem + "/__init__.py"} & tracked)
    return found


def import_module_literal(node):
    function = node.func
    name = function.attr if isinstance(function, ast.Attribute) else getattr(function, "id", None)
    first = node.args[0] if node.args else None
    if name == "import_module" and isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def reached_by(tree, path, tracked):
    own = posixpath.dirname(path)
    bases = (own, *SEARCH_ROOTS)
    runs_literals = not path.startswith("tests/")
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found |= module_files(alias.name, bases, tracked)
        elif isinstance(node, ast.ImportFrom):
            scope = bases
            if node.level:
                anchor = own
                for _ in range(node.level - 1):
                    anchor = posixpath.dirname(anchor)
                scope = (anchor,)
            module = node.module or ""
            for alias in node.names:
                found |= module_files(f"{module}.{alias.name}".lstrip("."), scope, tracked)
        elif isinstance(node, ast.Call) and (literal := import_module_literal(node)):
            found |= module_files(literal, bases, tracked)
        elif (runs_literals and isinstance(node, ast.Constant) and isinstance(node.value, str)
              and node.value.endswith(".py") and node.value in tracked):
            found.add(node.value)
    return found


def reached(starts, files, read, refusal):
    """`starts`' `.py` files and all they reach; an unparseable one raises `refusal`."""
    tracked = set(files)
    seen = {path for path in starts if path.endswith(".py")}
    pending = list(seen)
    while pending:
        path = pending.pop()
        try:
            tree = ast.parse(read(path), filename=path)
        except SyntaxError as error:
            raise refusal(
                f"cannot parse {path}, which a merge-gate job runs, so the "
                f"files it imports cannot be established: {error}") from error
        found = reached_by(tree, path, tracked) - seen
        seen |= found
        pending.extend(found)
    return seen
