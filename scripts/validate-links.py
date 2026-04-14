#!/usr/bin/env python3
"""Validate local Markdown links and anchors without external dependencies."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote


LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
EXCLUDED_DIRS = {".git", ".venv", ".pytest_cache"}


def iter_markdown_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.md")
        if not (EXCLUDED_DIRS & set(path.relative_to(root).parts))
    )


def github_anchor_slug(text: str) -> str:
    """Approximate GitHub's Markdown heading anchor generation for this repo."""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\s+", "-", text.strip().lower())
    return "".join(ch for ch in text if ch.isalnum() or ch in {"_", "-"}).strip("-")


def anchors_for(path: Path) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}

    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADING_RE.match(line)
        if not match:
            continue

        base = github_anchor_slug(match.group(2))
        if not base:
            continue

        count = counts.get(base, 0)
        counts[base] = count + 1
        anchors.add(base if count == 0 else f"{base}-{count}")

    return anchors


def iter_links(path: Path) -> list[tuple[int, str]]:
    links: list[tuple[int, str]] = []
    in_fence = False

    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue

        if in_fence:
            continue

        for raw_link in LINK_RE.findall(line):
            links.append((lineno, raw_link))

    return links


def validate(root: Path) -> int:
    markdown_files = iter_markdown_files(root)
    anchor_cache: dict[Path, set[str]] = {}
    broken_files: list[tuple[Path, int, str, Path]] = []
    broken_anchors: list[tuple[Path, int, str, Path, str]] = []
    checked = 0

    for path in markdown_files:
        for lineno, raw_link in iter_links(path):
            if raw_link.startswith(("http://", "https://", "mailto:", "tel:", "<")):
                continue

            if raw_link.startswith("#"):
                target = path
                anchor = raw_link[1:]
            else:
                target_part, _, anchor = raw_link.partition("#")
                target = (path.parent / unquote(target_part)).resolve()

            checked += 1

            if not target.exists():
                broken_files.append((path, lineno, raw_link, target))
                continue

            if not anchor:
                continue

            target_file = target / "README.md" if target.is_dir() and (target / "README.md").exists() else target
            if not target_file.is_file() or target_file.suffix.lower() != ".md":
                continue

            anchor_cache.setdefault(target_file, anchors_for(target_file))
            anchor = unquote(anchor).lower()
            if anchor not in anchor_cache[target_file]:
                broken_anchors.append((path, lineno, raw_link, target_file, anchor))

    if broken_files:
        print("Broken Markdown file links:", file=sys.stderr)
        for path, lineno, raw_link, target in broken_files:
            print(
                f"  {path.relative_to(root)}:{lineno}: {raw_link} -> {target}",
                file=sys.stderr,
            )

    if broken_anchors:
        print("Broken Markdown anchor links:", file=sys.stderr)
        for path, lineno, raw_link, target_file, anchor in broken_anchors:
            print(
                f"  {path.relative_to(root)}:{lineno}: {raw_link} -> "
                f"{target_file.relative_to(root)}#{anchor}",
                file=sys.stderr,
            )

    if broken_files or broken_anchors:
        return 1

    print(f"checked {checked} local Markdown links across {len(markdown_files)} files")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="repository root to scan",
    )
    args = parser.parse_args()
    return validate(Path(args.root).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
