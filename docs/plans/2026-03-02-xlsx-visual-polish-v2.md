# XLSX Visual Polish v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace 6 saturated XLSX palettes with 3 modern corporate palettes (with contrast control), and fix column width truncation, pie chart duplicate labels, and decimal precision.

**Architecture:** Swap the `_PALETTES` list (data-only change), add one field to `SheetPalette`, fix 3 isolated bugs in `_infer_chart_spec`, `_infer_number_format` keywords, and column width calculation. Update LLM prompts to reference new palette IDs.

**Tech Stack:** Python, openpyxl, pytest

---

### Task 1: Replace palettes with 3 corporate variants + add `header_contrast` field

**Files:**
- Modify: `core/studio/sheets/exporter_xlsx.py:49-158`

**Step 1: Add `header_contrast` field to `SheetPalette` dataclass**

At line 63 (after `trend_flat: str`), add:

```python
    header_contrast: str  # "light-on-dark" or "dark-on-light"
```

**Step 2: Replace the 6 `_PALETTES` entries with 3 new ones**

Replace lines 66-157 (the entire `_PALETTES` list) with:

```python
_PALETTES: List[SheetPalette] = [
    SheetPalette(
        id="slate-executive",
        name="Slate Executive",
        primary="2D3748",
        secondary="4A5568",
        accent="4A7AB5",
        background="F7FAFC",
        text="1A202C",
        header_text="FFFFFF",
        zebra="EDF2F7",
        subtotal="E2E8F0",
        trend_up="C6DAF0",
        trend_down="FED7D7",
        trend_flat="E2E8F0",
        header_contrast="light-on-dark",
    ),
    SheetPalette(
        id="iron-neutral",
        name="Iron Neutral",
        primary="1F2937",
        secondary="374151",
        accent="6B7280",
        background="F9FAFB",
        text="111827",
        header_text="FFFFFF",
        zebra="F3F4F6",
        subtotal="E5E7EB",
        trend_up="D1D5DB",
        trend_down="FEE2E2",
        trend_flat="E5E7EB",
        header_contrast="light-on-dark",
    ),
    SheetPalette(
        id="sand-warm",
        name="Sand Warm",
        primary="44403C",
        secondary="57534E",
        accent="B08D57",
        background="FAF9F6",
        text="292524",
        header_text="FFFFFF",
        zebra="F5F5F4",
        subtotal="E7E5E4",
        trend_up="E8DCCC",
        trend_down="FECACA",
        trend_flat="E7E5E4",
        header_contrast="light-on-dark",
    ),
]
```

**Step 3: Run tests to see what breaks**

Run: `PYTHONPATH=. uv run python -m pytest -q tests/test_studio_sheets_exporter_xlsx.py -v 2>&1 | tail -30`

Expected: Most tests PASS. Tests referencing old palette IDs (`forest-ledger`, `copper-report`) will FAIL — that's expected, we fix them in Task 5.

**Step 4: Commit**

```bash
git add core/studio/sheets/exporter_xlsx.py
git commit -m "Replace 6 saturated palettes with 3 modern corporate palettes"
```

---

### Task 2: Fix column width truncation

**Files:**
- Modify: `core/studio/sheets/exporter_xlsx.py:711-714`
- Test: `tests/test_studio_sheets_exporter_xlsx.py` (new test)

**Step 1: Write the failing test**

Add to `tests/test_studio_sheets_exporter_xlsx.py`:

```python
def test_xlsx_column_width_respects_header_length(tmp_path):
    path = tmp_path / "output.xlsx"
    tree = _make_tree(
        tabs=[
            SheetTab(
                id="t1",
                name="Data",
                headers=["Starting Customers", "Leads Generated", "V"],
                rows=[[50, 1000, 1]],
                formulas={},
                column_widths=[40, 40, 40],  # intentionally narrow pixel values
            )
        ]
    )
    export_to_xlsx(tree, path)
    wb = openpyxl.load_workbook(str(path))
    ws = wb.active
    # Column A header is 18 chars ("Starting Customers"), needs at least 22 width
    # The narrow column_width of 40 (40/7 ≈ 5.7) must NOT win over header length
    assert ws.column_dimensions["A"].width >= len("Starting Customers") + 2
    # Column C header is 1 char ("V"), pixel width 40/7 ≈ 5.7 is fine
    assert ws.column_dimensions["C"].width >= 5
    wb.close()
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run python -m pytest -q tests/test_studio_sheets_exporter_xlsx.py::test_xlsx_column_width_respects_header_length -v`

Expected: FAIL — column A width will be ~5.7 (40/7), less than 20.

**Step 3: Fix the column width calculation**

Replace lines 711-714:

```python
        if tab.column_widths:
            for col_idx, width in enumerate(tab.column_widths, start=1):
                col_letter = get_column_letter(col_idx)
                ws.column_dimensions[col_letter].width = max(width / 7, 8)
```

With:

```python
        if tab.column_widths:
            for col_idx, width in enumerate(tab.column_widths, start=1):
                col_letter = get_column_letter(col_idx)
                header_len = len(str(tab.headers[col_idx - 1])) + 4 if col_idx - 1 < len(tab.headers) else 10
                max_data_len = max(
                    (len(str(row[col_idx - 1]))
                     for row in tab.rows
                     if col_idx - 1 < len(row) and row[col_idx - 1] is not None),
                    default=0,
                )
                data_width = min(max_data_len + 2, 50)
                ws.column_dimensions[col_letter].width = max(width / 7, header_len, data_width, 10)
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. uv run python -m pytest -q tests/test_studio_sheets_exporter_xlsx.py::test_xlsx_column_width_respects_header_length -v`

Expected: PASS

**Step 5: Commit**

```bash
git add core/studio/sheets/exporter_xlsx.py tests/test_studio_sheets_exporter_xlsx.py
git commit -m "Fix column width truncation: ensure headers are never clipped"
```

---

### Task 3: Fix pie chart duplicate legend labels

**Files:**
- Modify: `core/studio/sheets/exporter_xlsx.py:507-511`
- Test: `tests/test_studio_sheets_exporter_xlsx.py` (new test)

**Step 1: Write the failing test**

Add to `tests/test_studio_sheets_exporter_xlsx.py`:

```python
def test_xlsx_pie_chart_skipped_for_duplicate_categories(tmp_path):
    """When category column has many duplicates, should use bar instead of pie."""
    path = tmp_path / "output.xlsx"
    tree = _make_tree(
        tabs=[
            SheetTab(
                id="t1",
                name="Data",
                headers=["Category", "Metric", "Value"],
                rows=[
                    ["General", "Metric A", 100],
                    ["General", "Metric B", 200],
                    ["General", "Metric C", 150],
                    ["Pricing", "Metric D", 300],
                    ["Pricing", "Metric E", 250],
                    ["Cost", "Metric F", 80],
                ],
                formulas={},
                column_widths=[120, 120, 80],
            )
        ],
    )
    export_to_xlsx(tree, path)
    wb = openpyxl.load_workbook(str(path))
    ws = wb.active
    charts = getattr(ws, "_charts", [])
    # Should have a chart, but NOT a pie chart (categories have duplicates)
    for chart in charts:
        assert not isinstance(chart, openpyxl.chart.PieChart), \
            "Pie chart should not be used when categories have many duplicates"
    wb.close()
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run python -m pytest -q tests/test_studio_sheets_exporter_xlsx.py::test_xlsx_pie_chart_skipped_for_duplicate_categories -v`

Expected: FAIL — currently picks pie because 3 unique categories <= 8.

**Step 3: Fix the chart type heuristic**

Replace lines 507-511:

```python
    else:
        unique_categories = {
            str(v).strip() for v in cat_values if v is not None and str(v).strip()
        }
        chart_type = "pie" if len(unique_categories) <= 8 else "bar"
```

With:

```python
    else:
        unique_categories = {
            str(v).strip() for v in cat_values if v is not None and str(v).strip()
        }
        if len(unique_categories) <= 8 and len(unique_categories) >= len(cat_values) * 0.7:
            chart_type = "pie"
        else:
            chart_type = "bar"
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. uv run python -m pytest -q tests/test_studio_sheets_exporter_xlsx.py::test_xlsx_pie_chart_skipped_for_duplicate_categories -v`

Expected: PASS

**Step 5: Commit**

```bash
git add core/studio/sheets/exporter_xlsx.py tests/test_studio_sheets_exporter_xlsx.py
git commit -m "Fix pie chart: skip pie when categories have duplicate labels"
```

---

### Task 4: Expand number format keywords

**Files:**
- Modify: `core/studio/sheets/exporter_xlsx.py:31-41`
- Test: `tests/test_studio_sheets_exporter_xlsx.py` (new test)

**Step 1: Write the failing test**

Add to `tests/test_studio_sheets_exporter_xlsx.py`:

```python
def test_xlsx_mrr_column_gets_currency_format(tmp_path):
    path = tmp_path / "output.xlsx"
    tree = _make_tree(
        tabs=[
            SheetTab(
                id="t1",
                name="Revenue",
                headers=["Month", "Total MRR", "Churn Rate"],
                rows=[["Jan", 7900.123, 0.02], ["Feb", 10946.456, 0.03]],
                formulas={},
                column_widths=[100, 100, 100],
            )
        ]
    )
    export_to_xlsx(tree, path)
    wb = openpyxl.load_workbook(str(path))
    ws = wb.active
    # "Total MRR" should get currency format (contains "mrr")
    mrr_cell = ws.cell(row=2, column=2)
    assert "$" in mrr_cell.number_format or "#,##0" in mrr_cell.number_format, \
        f"MRR column should have currency/number format, got: {mrr_cell.number_format}"
    # "Churn Rate" should get percent format (contains "churn" or "rate")
    churn_cell = ws.cell(row=2, column=3)
    assert "%" in churn_cell.number_format, \
        f"Churn Rate column should have percent format, got: {churn_cell.number_format}"
    wb.close()
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run python -m pytest -q tests/test_studio_sheets_exporter_xlsx.py::test_xlsx_mrr_column_gets_currency_format -v`

Expected: FAIL — "mrr" and "churn" are not in the keyword sets.

**Step 3: Expand the keyword sets**

Replace lines 31-41:

```python
_CURRENCY_KEYWORDS = {
    "amount",
    "revenue",
    "cost",
    "price",
    "budget",
    "profit",
    "expense",
    "sales",
}
_PERCENT_KEYWORDS = {"pct", "percent", "%", "growth", "rate", "ratio", "margin"}
```

With:

```python
_CURRENCY_KEYWORDS = {
    "amount",
    "revenue",
    "cost",
    "price",
    "budget",
    "profit",
    "expense",
    "sales",
    "mrr",
    "arr",
    "arpu",
    "cltv",
    "ltv",
    "income",
    "balance",
    "salary",
    "spend",
    "fee",
}
_PERCENT_KEYWORDS = {"pct", "percent", "%", "growth", "rate", "ratio", "margin", "churn"}
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. uv run python -m pytest -q tests/test_studio_sheets_exporter_xlsx.py::test_xlsx_mrr_column_gets_currency_format -v`

Expected: PASS

**Step 5: Commit**

```bash
git add core/studio/sheets/exporter_xlsx.py tests/test_studio_sheets_exporter_xlsx.py
git commit -m "Expand number format keywords: add MRR, ARR, churn, etc."
```

---

### Task 5: Update prompts and fix palette-specific tests

**Files:**
- Modify: `core/studio/prompts.py:270,350`
- Modify: `tests/test_studio_sheets_exporter_xlsx.py` (fix 2 existing tests, add 1 new test)

**Step 1: Update palette IDs in prompts.py**

At line 270, replace:

```
"palette_hint": "oceanic-blue|forest-ledger|sunset-ops|graphite-finance|teal-analytics|copper-report",
```

With:

```
"palette_hint": "slate-executive|iron-neutral|sand-warm",
```

At line 350, make the same replacement.

**Step 2: Fix `test_xlsx_palette_hint_overrides_hash`**

Replace `"copper-report"` with `"sand-warm"` in both the metadata and the assertion (2 places in the test).

**Step 3: Fix `test_xlsx_conditional_formatting_uses_palette_colors`**

Replace `"forest-ledger"` with `"slate-executive"` in the metadata and `_PALETTE_BY_ID` lookup (2 places in the test).

**Step 4: Add new test for `header_contrast` field**

```python
def test_xlsx_all_palettes_have_header_contrast():
    from core.studio.sheets.exporter_xlsx import _PALETTES
    for palette in _PALETTES:
        assert hasattr(palette, "header_contrast"), f"Palette {palette.id} missing header_contrast"
        assert palette.header_contrast in ("light-on-dark", "dark-on-light"), \
            f"Palette {palette.id} has invalid header_contrast: {palette.header_contrast}"
```

**Step 5: Run all affected tests**

Run: `PYTHONPATH=. uv run python -m pytest -q tests/test_studio_sheets_exporter_xlsx.py tests/test_studio_sheets_validator.py -v`

Expected: ALL PASS

**Step 6: Commit**

```bash
git add core/studio/prompts.py tests/test_studio_sheets_exporter_xlsx.py
git commit -m "Update prompts and tests for new corporate palette IDs"
```

---

### Task 6: Full verification

**Step 1: Run full backend test suite**

Run: `PYTHONPATH=. uv run python -m pytest -q tests -m "not integration and not external" 2>&1 | tail -5`

Expected: All tests pass (894+ tests, 0 failures).

**Step 2: Visual smoke test**

Run:
```bash
PYTHONPATH=. uv run python -c "
from core.schemas.studio_schema import SheetContentTree, SheetTab
from core.studio.sheets.exporter_xlsx import export_to_xlsx, _PALETTES
from pathlib import Path
for p in _PALETTES:
    tree = SheetContentTree(
        workbook_title=f'Test {p.name}',
        tabs=[SheetTab(id='t1', name='Data',
            headers=['Month','Total MRR','Cost','Growth Rate'],
            rows=[['Jan',7900,6320,0.05],['Feb',10946.46,8757,0.08],['Mar',14121.83,11297,0.12],['','Total',26374,'']],
            formulas={}, column_widths=[100,100,80,100])],
        metadata={'palette_hint': p.id, 'visual_profile': 'balanced'})
    export_to_xlsx(tree, Path(f'/tmp/test_{p.id}.xlsx'))
    print(f'Exported: {p.id}')
"
```

Expected: 3 files exported, open each to verify visual quality.

**Step 3: Report results**

Report test counts and any failures. Open the 3 XLSX files and confirm:
- Headers are NOT truncated
- Colors are muted/corporate (not saturated)
- Data bars use the palette accent color
- Number formatting shows `$` for MRR, `%` for Growth Rate
