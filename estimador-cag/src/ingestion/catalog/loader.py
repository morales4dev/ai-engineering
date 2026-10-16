"""Load and validate the YAML catalog.

Reads a YAML file with ``yaml.safe_load``, validates it against
:class:`DataCatalog`. The two-line ``load_catalog`` is intentionally trivial —
all the heavy lifting (decision rules, duplicate detection) lives in the
model, not here.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from ingestion.catalog.models import DataCatalog


def load_catalog(path: str | Path) -> DataCatalog:
    """Parse ``path`` as YAML and validate as a :class:`DataCatalog`."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return DataCatalog.model_validate(raw)


def format_catalog_errors(exc: ValidationError) -> str:
    """One line per field. The CLI prints this instead of a Pydantic traceback."""
    lines = ["Catalog inválido:"]
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"])
        lines.append(f"  {loc}: {err['msg']}")
    return "\n".join(lines)


def _main(argv: list[str]) -> int:
    """CLI: ``python -m ingestion.catalog.loader data/catalog/catalog.yaml``."""
    if len(argv) != 2:
        print("usage: python -m ingestion.catalog.loader <path.yaml>")
        return 1
    try:
        catalog = load_catalog(argv[1])
    except ValidationError as exc:
        print(format_catalog_errors(exc), file=sys.stderr)
        return 1
    included = catalog.included_sources()
    print(f"Catalog version: {catalog.version}")
    print(f"Sources total:  {len(catalog.sources)}")
    print(f"Sources included: {len(included)}")
    for src in included:
        print(f"  - {src.name} ({src.format}) — {src.description!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
