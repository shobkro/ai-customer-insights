"""The generated Power BI project only references tables, columns and measures that exist."""
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "build_pbip", ROOT / "scripts" / "07_build_powerbi_project.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

COLUMNS = (
    {(t, c) for t, cols in build.TABLES.items() for c, _, _ in cols}
    | {(t, name) for t, name, _, _ in build.CALC_COLUMNS}
    | {("fact_reviews", "review_key"), ("review_ai_labels", "review_key")}
)
MEASURES = {name for name, *_ in build.MEASURES}


def fields(obj):
    """Yield every Column / Measure reference inside a visual definition."""
    if isinstance(obj, dict):
        for kind in ("Column", "Measure"):
            ref = obj.get(kind)
            if isinstance(ref, dict) and "Entity" in ref.get("Expression", {}).get("SourceRef", {}):
                yield kind, ref["Expression"]["SourceRef"]["Entity"], ref["Property"]
        for value in obj.values():
            yield from fields(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from fields(value)


def test_visuals_reference_real_fields():
    visuals = [v for p in build.build_pages() for v in p.visuals]
    assert len(visuals) > 20
    for v in visuals:
        for kind, table, prop in fields(v):
            if kind == "Measure":
                assert table == "_Measures" and prop in MEASURES, (v["name"], prop)
            else:
                assert (table, prop) in COLUMNS, (v["name"], table, prop)


def test_dax_references_exist():
    exprs = [(n, d) for n, d, *_ in build.MEASURES] + [(n, d) for _, n, d, _ in build.CALC_COLUMNS]
    for name, dax in exprs:
        for table, column in re.findall(r"(\w+)\[([^\]]+)\]", dax):
            assert (table, column) in COLUMNS, (name, table, column)
        for measure in re.findall(r"(?<![\w\]])\[([^\]]+)\]", dax):
            assert measure in MEASURES, (name, measure)


def test_relationships_use_real_columns():
    for from_t, from_c, to_t, to_c, _ in build.RELATIONSHIPS:
        assert (from_t, from_c) in COLUMNS and (to_t, to_c) in COLUMNS


def test_committed_project_is_up_to_date():
    """Every visual the generator makes is in the committed report folder."""
    pages_dir = build.REPORT_DIR / "definition" / "pages"
    order = json.loads((pages_dir / "pages.json").read_text(encoding="utf-8"))["pageOrder"]
    pages = build.build_pages()
    assert order == [p.name for p in pages]
    for p in pages:
        for v in p.visuals:
            assert (pages_dir / p.name / "visuals" / v["name"] / "visual.json").exists()
