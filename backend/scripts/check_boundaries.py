#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path

DOMAIN_BANNED_EXTERNAL = {
    "sqlalchemy",
    "redis",
    "celery",
    "fastapi",
    "pydantic",
    "pydantic_settings",
}

APP_BANNED_EXTERNAL = {
    "sqlalchemy",
    "redis",
    "celery",
    "fastapi",
    "pydantic",
    "pydantic_settings",
}

API_BANNED_EXTERNAL = {
    "sqlalchemy",
    "redis",
    "celery",
}

WORKER_BANNED_EXTERNAL = {
    "sqlalchemy",
    "redis",
}

LAYER_NAMES = ("api", "worker", "tasks", "application", "domain", "infrastructure")

NO_INTERFACE_IMPORT_RULES = {
    ("typing", "Protocol"),
    ("typing_extensions", "Protocol"),
    ("abc", "ABC"),
    ("abc", "ABCMeta"),
    ("abc", "abstractmethod"),
}
NO_INTERFACE_BASES = {"Protocol", "ABC", "ABCMeta"}


@dataclass(frozen=True)
class ImportRef:
    module: str
    lineno: int


def _classify_layer(py_file: Path, *, pkg_root: Path) -> str | None:
    rel = py_file.relative_to(pkg_root)
    if not rel.parts:
        return None
    top = rel.parts[0]
    return top if top in LAYER_NAMES else None


def _normalize_module(module: str, package: str | None) -> str:
    if package and module.startswith(package + "."):
        return module[len(package) + 1 :]
    return module


def _extract_imports(py_path: Path) -> list[ImportRef]:
    tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    found: list[ImportRef] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append(ImportRef(module=alias.name, lineno=node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.append(ImportRef(module=node.module, lineno=node.lineno))
    return found


def _extract_no_interface_violations(py_path: Path) -> list[str]:
    tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    violations: list[str] = []
    banned_base_aliases = set(NO_INTERFACE_BASES)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if (node.module, alias.name) in NO_INTERFACE_IMPORT_RULES:
                    local_name = alias.asname or alias.name
                    violations.append(
                        f"{py_path}:{node.lineno} no-interfaces rule: forbidden import "
                        f"'{node.module}.{alias.name}'"
                    )
                    if alias.name in NO_INTERFACE_BASES:
                        banned_base_aliases.add(local_name)

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        for base in node.bases:
            symbol = _base_symbol(base)
            if symbol is None:
                continue
            if symbol in banned_base_aliases or symbol in NO_INTERFACE_BASES:
                violations.append(
                    f"{py_path}:{node.lineno} no-interfaces rule: class '{node.name}' "
                    f"must not inherit from '{symbol}'"
                )

    return violations


def _base_symbol(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _base_symbol(node.value)
    return None


def _is_internal_layer(top: str) -> bool:
    return top in LAYER_NAMES


def _candidate_packages(parent: Path) -> list[str]:
    candidates: list[str] = []
    for child in sorted(parent.iterdir()):
        if not child.is_dir():
            continue
        if (child / "__init__.py").exists():
            candidates.append(child.name)
    return candidates


def _resolve_package_root(repo_root: Path, package: str | None) -> tuple[str, Path]:
    src_dir = repo_root / "src"
    if package:
        if (src_dir / package).exists():
            return package, src_dir / package
        if (repo_root / package).exists():
            return package, repo_root / package
        raise SystemExit(f"Package root not found for package '{package}' under {repo_root}")

    if src_dir.exists():
        candidates = _candidate_packages(src_dir)
        if len(candidates) == 1:
            return candidates[0], src_dir / candidates[0]
        if not candidates:
            raise SystemExit(f"Could not auto-detect package under {src_dir} (no packages with __init__.py).")
        raise SystemExit(
            "Multiple packages found under src/. Pass --package explicitly. "
            f"Candidates: {', '.join(candidates)}"
        )

    candidates = _candidate_packages(repo_root)
    if "app" in candidates:
        return "app", repo_root / "app"
    if len(candidates) == 1:
        return candidates[0], repo_root / candidates[0]
    if not candidates:
        raise SystemExit(
            "Could not auto-detect package at repo root (no packages with __init__.py). "
            "Expected src/<package> or <package>/ layout."
        )
    raise SystemExit(
        "Multiple packages found at repo root. Pass --package explicitly. "
        f"Candidates: {', '.join(candidates)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check layering/import boundaries for API/Worker→Application→Infrastructure→Domain "
            "(supports src/<package> and <package>/ layouts)."
        )
    )
    parser.add_argument("--root", default=".", help="Repository root (default: current directory).")
    parser.add_argument(
        "--package",
        default=None,
        help="Python package name (auto-detect when omitted).",
    )
    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    package, pkg_root = _resolve_package_root(repo_root, args.package)
    if not pkg_root.exists():
        raise SystemExit(f"Package root not found: {pkg_root}")

    violations: list[str] = []
    py_files = sorted(p for p in pkg_root.rglob("*.py") if p.is_file())
    for py_file in py_files:
        violations.extend(_extract_no_interface_violations(py_file))

        layer = _classify_layer(py_file, pkg_root=pkg_root)
        if layer is None:
            continue

        for imp in _extract_imports(py_file):
            normalized = _normalize_module(imp.module, package)
            top = normalized.split(".", 1)[0]

            # External bans by layer
            if layer == "domain" and top in DOMAIN_BANNED_EXTERNAL:
                violations.append(f"{py_file}:{imp.lineno} domain imports banned external module: {imp.module}")
            if layer == "application" and top in APP_BANNED_EXTERNAL:
                violations.append(
                    f"{py_file}:{imp.lineno} application imports banned external module: {imp.module}"
                )
            if layer == "api" and top in API_BANNED_EXTERNAL:
                violations.append(f"{py_file}:{imp.lineno} api imports banned external module: {imp.module}")
            if layer == "worker" and top in WORKER_BANNED_EXTERNAL:
                violations.append(
                    f"{py_file}:{imp.lineno} worker imports banned external module: {imp.module}"
                )
            if layer == "tasks" and top in WORKER_BANNED_EXTERNAL:
                violations.append(
                    f"{py_file}:{imp.lineno} tasks imports banned external module: {imp.module}"
                )

            # Internal direction constraints
            if layer == "domain" and _is_internal_layer(top) and top != "domain":
                violations.append(f"{py_file}:{imp.lineno} domain must not depend on {top}: {imp.module}")
            if layer == "infrastructure" and _is_internal_layer(top) and top in {"api", "worker", "application"}:
                violations.append(
                    f"{py_file}:{imp.lineno} infrastructure must not depend on {top}: {imp.module}"
                )
            if layer == "application" and _is_internal_layer(top) and top in {"api", "worker"}:
                violations.append(
                    f"{py_file}:{imp.lineno} application must not depend on {top}: {imp.module}"
                )
            if layer == "api" and _is_internal_layer(top) and top == "infrastructure":
                violations.append(f"{py_file}:{imp.lineno} api must not depend on infrastructure: {imp.module}")
            if layer == "worker" and _is_internal_layer(top) and top == "infrastructure":
                violations.append(f"{py_file}:{imp.lineno} worker must not depend on infrastructure: {imp.module}")
            if layer == "worker" and _is_internal_layer(top) and top == "api":
                violations.append(f"{py_file}:{imp.lineno} worker must not depend on api: {imp.module}")
            if layer == "tasks" and _is_internal_layer(top) and top in {"infrastructure", "api"}:
                violations.append(
                    f"{py_file}:{imp.lineno} tasks must not depend on {top}: {imp.module}"
                )

    if violations:
        print("Boundary violations found:\n")
        for v in violations:
            print("-", v)
        return 1

    print(f"No boundary violations under {pkg_root} (package={package})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
