# Forge Phase 2 — Implementation Plan: Slides MVP + PPTX Export (Days 6-8)

## Context

Phase 1 (Days 1-5) delivered the foundational layer for Forge: canonical Pydantic schemas for Slides/Docs/Sheets, outline-first orchestration pipeline, file-based storage with revision tracking, LLM prompt templates, and 8 API endpoints — all backed by 65+ tests across 5 test files.

Phase 2 builds directly on Phase 1 to deliver a production-usable Slides MVP:

- **Deterministic slide generation** with seed-based structural planning
- **Curated theme system** (8 base themes with colors + fonts)
- **PPTX export** using `python-pptx` with programmatic shape rendering
- **Open-validation** to verify exported files aren't corrupt
- **Export job tracking** with persistence and API endpoints

### Scope Boundaries

**In scope:**
- Slide type registry with constants for 10 slide types and 8 element types
- Deterministic slide sequence planner (`compute_seed()`, `clamp_slide_count()`, `plan_slide_sequence()`)
- 8 curated themes with exact hex colors and font pairings
- PPTX exporter with 10 slide-type renderer functions, speaker notes, and theme color application
- PPTX validator (open-validation by reloading with python-pptx)
- Export job lifecycle (creation, persistence, retrieval, download)
- 6 new API endpoints for export and theme operations
- Enhanced prompts for better slides quality
- 78 new tests across 5 new test files + updates to 2 existing test files

**Out of scope:**
- Phase 3 quality pass (100+ procedural theme variants, advanced layout-quality scoring with pixel-level analysis, chart rendering quality)
- Document and Sheet export engines (Phase 4-5)
- PDF/HTML/Google Slides export formats
- Chat-driven edit loop and patch engine (Phase 6)
- Full frontend WYSIWYG slide editor (separate frontend track)
- Pixel-level overflow detection and advanced layout scoring beyond text-length heuristics
- Image generation or embedding (deferred)

### Codebase Patterns Referenced

| Pattern | Source File | What to Replicate |
|---------|-----------|-------------------|
| Pydantic schemas | `core/schemas/studio_schema.py` | Enum + BaseModel with Field defaults |
| Router structure | `routers/studio.py` | Existing Phase 1 router, add new endpoints |
| File persistence | `core/studio/storage.py` | `StudioStorage` directory layout + JSON serialization |
| Orchestrator flow | `core/studio/orchestrator.py` | `ForgeOrchestrator` pipeline methods |
| Prompt templates | `core/studio/prompts.py` | `get_outline_prompt()` / `get_draft_prompt()` pattern |
| Lazy singleton | `shared/state.py` | `_instance = None` + `get_*()` accessor |
| Error handling | `routers/studio.py:52-72` | `try/except ValidationError/ValueError/Exception` → HTTP status codes |

---

## 1. Directory & File Structure

```
Arcturus/
├── core/
│   ├── schemas/
│   │   └── studio_schema.py                          # MODIFY — add ExportFormat, ExportStatus, ExportJob, SlideThemeColors, SlideTheme, Artifact.exports
│   └── studio/
│       ├── orchestrator.py                           # MODIFY — add export_artifact() method
│       ├── storage.py                                # MODIFY — add export job persistence methods
│       ├── prompts.py                                # MODIFY — enhance slides prompts with speaker notes, slide types, sequence hints
│       └── slides/
│           ├── __init__.py                           # NEW (package init)
│           ├── types.py                              # NEW — slide type + element type constants, mapping
│           ├── themes.py                             # NEW — 8 curated themes, get_theme(), list_themes()
│           ├── generator.py                          # NEW — deterministic planner: compute_seed(), clamp_slide_count(), plan_slide_sequence()
│           ├── exporter.py                           # NEW — PPTX renderer: 10 slide-type functions + export_to_pptx()
│           └── validator.py                          # NEW — open-validation: validate_pptx()
├── routers/
│   └── studio.py                                     # MODIFY — add 6 export/theme endpoints, fix route ordering
├── pyproject.toml                                    # MODIFY — add python-pptx dependency
├── tests/
│   ├── test_studio_slides_types.py                   # NEW — 8 tests
│   ├── test_studio_slides_themes.py                  # NEW — 10+ tests
│   ├── test_studio_slides_generator.py               # NEW — 10+ tests
│   ├── test_studio_slides_exporter.py                # NEW — 12+ tests
│   ├── test_studio_export_router.py                  # NEW — 8+ tests
│   ├── acceptance/p04_forge/test_exports_open_and_render.py  # MODIFY — add 8 functional tests
│   └── integration/test_forge_research_to_slides.py          # MODIFY — add 5 functional tests
└── studio/                                           # RUNTIME — export files stored here
    └── {artifact_id}/
        └── exports/
            ├── {export_job_id}.json                  # Export job metadata
            └── {export_job_id}.pptx                  # Generated PPTX file
```

**Total: 6 new files + 7 modified files + 5 new test files + 2 modified test files**

---

## 2. Schema Additions

**File:** `core/schemas/studio_schema.py`

### 2.1 New Enums

```python
class ExportFormat(str, Enum):
    pptx = "pptx"
    # Future: docx, xlsx, pdf — added in Phase 4-5


class ExportStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
```

### 2.2 Export Job Model

```python
class ExportJob(BaseModel):
    id: str
    artifact_id: str
    format: ExportFormat
    status: ExportStatus = ExportStatus.pending
    output_uri: Optional[str] = None
    file_size_bytes: Optional[int] = None
    validator_results: Optional[Dict[str, Any]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
```

### 2.2b Export Job Summary Model

```python
class ExportJobSummary(BaseModel):
    id: str
    format: str
    status: str
    created_at: datetime
```

### 2.3 Theme Models

```python
class SlideThemeColors(BaseModel):
    primary: str          # Hex color, e.g. "#1B365D"
    secondary: str        # Hex color
    accent: str           # Hex color
    background: str       # Hex color
    text: str             # Hex color
    text_light: str       # Hex color for subtitles/captions


class SlideTheme(BaseModel):
    id: str               # e.g. "corporate-blue"
    name: str             # e.g. "Corporate Blue"
    colors: SlideThemeColors
    font_heading: str     # e.g. "Calibri"
    font_body: str        # e.g. "Calibri Light"
    description: Optional[str] = None
```

### 2.4 Artifact Model Update

Add `exports` field to `Artifact`:

```python
class Artifact(BaseModel):
    id: str
    type: ArtifactType
    title: str
    created_at: datetime
    updated_at: datetime
    schema_version: str = "1.0"
    model: Optional[str] = None
    content_tree: Optional[Dict[str, Any]] = None
    theme_id: Optional[str] = None
    revision_head_id: Optional[str] = None
    outline: Optional[Outline] = None
    exports: List[ExportJobSummary] = Field(default_factory=list)  # NEW — typed export job summaries
```

**Backward compatibility:** The `exports` field has `default_factory=list`, so existing artifact JSON files without an `exports` key will deserialize correctly with an empty list. No migration needed.

---

## 3. Slide Type Registry

**File:** `core/studio/slides/types.py`

### 3.1 Slide Type Constants

```python
# 10 supported slide types
SLIDE_TYPES = {
    "title",
    "content",
    "two_column",
    "comparison",
    "timeline",
    "chart",
    "image_text",
    "quote",
    "code",
    "team",
}

# 8 supported element types
ELEMENT_TYPES = {
    "title",
    "subtitle",
    "body",
    "bullet_list",
    "image",
    "chart",
    "code",
    "quote",
}
```

### 3.2 Slide-Type-to-Element Mapping

Defines which element types are valid for each slide type. Used by the generator to plan element composition and by the exporter to select rendering functions.

```python
SLIDE_TYPE_ELEMENTS = {
    "title":       ["title", "subtitle"],
    "content":     ["title", "body", "bullet_list"],
    "two_column":  ["title", "body", "bullet_list"],
    "comparison":  ["title", "body", "bullet_list"],
    "timeline":    ["title", "body", "bullet_list"],
    "chart":       ["title", "chart", "body"],
    "image_text":  ["title", "image", "body"],
    "quote":       ["quote", "body"],
    "code":        ["title", "code", "body"],
    "team":        ["title", "body", "bullet_list"],
}
```

### 3.3 Narrative Arc Constants

Defines the default structural pattern for slide sequences:

```python
# Narrative arc pattern for planning slide sequences
NARRATIVE_ARC = [
    "title",         # Opening
    "content",       # Context / Problem
    "content",       # Deep dive
    "two_column",    # Comparison or two-sided view
    "timeline",      # Progression or roadmap
    "chart",         # Data evidence
    "quote",         # Testimonial or key insight
    "content",       # Solution / Next steps
    "team",          # Team or credits (optional)
    "title",         # Closing / CTA
]
```

### 3.4 Validation Helper

```python
def is_valid_slide_type(slide_type: str) -> bool:
    return slide_type in SLIDE_TYPES

def is_valid_element_type(element_type: str) -> bool:
    return element_type in ELEMENT_TYPES

def get_elements_for_slide_type(slide_type: str) -> list[str]:
    return SLIDE_TYPE_ELEMENTS.get(slide_type, ["title", "body"])
```

### 3.5 Schema Validation Strategy

Phase 2 uses soft validation: `Slide.slide_type` and `SlideElement.type` remain `str` fields in the Pydantic schema. The `is_valid_slide_type()` and `is_valid_element_type()` helpers in `types.py` are available for explicit checks, and the exporter falls back to `_render_content` for unknown types. This avoids breaking the pipeline when the LLM produces unexpected type names.

Phase 3 may add Pydantic validators that warn or reject on unknown types once LLM output patterns are stable.

---

## 4. Theme System

**File:** `core/studio/slides/themes.py`

### 4.1 Design Principles

- **Data-driven:** Themes are plain `SlideTheme` instances in a dict, not subclasses or config files
- **Fallback:** Unknown theme IDs resolve to `"corporate-blue"` (the default)
- **Phase 3 hook:** The `SlideTheme` model is deliberately minimal. Phase 3 adds `variant_seed`, `gradient_stops`, and procedural generation — those fields will be `Optional` additions, not breaking changes

### 4.2 Curated Theme Catalog (8 themes)

```python
from core.schemas.studio_schema import SlideTheme, SlideThemeColors

_THEMES: dict[str, SlideTheme] = {}

def _register(theme: SlideTheme) -> None:
    _THEMES[theme.id] = theme

_register(SlideTheme(
    id="corporate-blue",
    name="Corporate Blue",
    colors=SlideThemeColors(
        primary="#1B365D",
        secondary="#4A90D9",
        accent="#F5A623",
        background="#FFFFFF",
        text="#1B365D",
        text_light="#6B7B8D",
    ),
    font_heading="Calibri",
    font_body="Calibri Light",
    description="Clean, professional theme suitable for enterprise presentations",
))

_register(SlideTheme(
    id="startup-bold",
    name="Startup Bold",
    colors=SlideThemeColors(
        primary="#FF6B35",
        secondary="#004E64",
        accent="#25A18E",
        background="#F7F7F7",
        text="#1A1A2E",
        text_light="#6C757D",
    ),
    font_heading="Montserrat",
    font_body="Open Sans",
    description="Energetic theme for startup pitch decks and product launches",
))

_register(SlideTheme(
    id="minimal-light",
    name="Minimal Light",
    colors=SlideThemeColors(
        primary="#2D2D2D",
        secondary="#757575",
        accent="#00BCD4",
        background="#FAFAFA",
        text="#212121",
        text_light="#9E9E9E",
    ),
    font_heading="Helvetica",
    font_body="Helvetica Light",
    description="Minimalist theme with clean typography and subtle accents",
))

_register(SlideTheme(
    id="nature-green",
    name="Nature Green",
    colors=SlideThemeColors(
        primary="#2E7D32",
        secondary="#81C784",
        accent="#FF8F00",
        background="#F1F8E9",
        text="#1B5E20",
        text_light="#689F38",
    ),
    font_heading="Georgia",
    font_body="Lato",
    description="Organic theme for sustainability, environment, and nature topics",
))

_register(SlideTheme(
    id="tech-dark",
    name="Tech Dark",
    colors=SlideThemeColors(
        primary="#00E5FF",
        secondary="#7C4DFF",
        accent="#FF4081",
        background="#121212",
        text="#E0E0E0",
        text_light="#9E9E9E",
    ),
    font_heading="Roboto",
    font_body="Roboto Light",
    description="Dark mode theme for technology and developer-focused decks",
))

_register(SlideTheme(
    id="warm-terracotta",
    name="Warm Terracotta",
    colors=SlideThemeColors(
        primary="#C75B39",
        secondary="#D4956A",
        accent="#5B8C5A",
        background="#FFF8F0",
        text="#3E2723",
        text_light="#8D6E63",
    ),
    font_heading="Playfair Display",
    font_body="Source Sans Pro",
    description="Warm, earthy theme for creative and lifestyle presentations",
))

_register(SlideTheme(
    id="ocean-gradient",
    name="Ocean Gradient",
    colors=SlideThemeColors(
        primary="#006994",
        secondary="#40C4FF",
        accent="#FFAB40",
        background="#E3F2FD",
        text="#01579B",
        text_light="#4FC3F7",
    ),
    font_heading="Poppins",
    font_body="Nunito",
    description="Calming ocean-inspired theme with gradient accents",
))

_register(SlideTheme(
    id="monochrome-pro",
    name="Monochrome Pro",
    colors=SlideThemeColors(
        primary="#000000",
        secondary="#424242",
        accent="#F44336",
        background="#FFFFFF",
        text="#212121",
        text_light="#757575",
    ),
    font_heading="Arial",
    font_body="Arial",
    description="High-contrast black and white theme with red accent",
))
```

### 4.3 Public API

```python
DEFAULT_THEME_ID = "corporate-blue"

def get_theme(theme_id: str | None = None) -> SlideTheme:
    """Resolve theme by ID, falling back to default if not found."""
    if theme_id is None:
        return _THEMES[DEFAULT_THEME_ID]
    return _THEMES.get(theme_id, _THEMES[DEFAULT_THEME_ID])

def list_themes() -> list[SlideTheme]:
    """Return all available themes as a list."""
    return list(_THEMES.values())

def get_theme_ids() -> list[str]:
    """Return all available theme IDs."""
    return list(_THEMES.keys())
```

---

## 5. Deterministic Generator

**File:** `core/studio/slides/generator.py`

### 5.1 Design

The generator provides deterministic structural planning for slide decks. Given the same inputs, the **slide count contract** [8-15] is enforced post-generation via `enforce_slide_count()`. The planned slide type sequence is advisory (injected as prompt guidance); the LLM's actual type choices are rendered as-is, with unknown types falling back to `_render_content`. The LLM fills in content (prose varies), but the slide count range is guaranteed.

### 5.2 Seed Computation

```python
import hashlib

def compute_seed(artifact_id: str) -> int:
    """Compute a deterministic seed from artifact ID.

    Returns an integer seed for use with random.Random().
    """
    raw = artifact_id
    return int(hashlib.sha256(raw.encode()).hexdigest()[:8], 16)
```

### 5.3 Slide Count Clamping

```python
MIN_SLIDES = 8
MAX_SLIDES = 15
DEFAULT_SLIDES = 10

def clamp_slide_count(requested: int | None = None) -> int:
    """Clamp requested slide count to [8, 15] range.

    Returns DEFAULT_SLIDES if requested is None.
    """
    if requested is None:
        return DEFAULT_SLIDES
    return max(MIN_SLIDES, min(MAX_SLIDES, requested))
```

### 5.4 Slide Sequence Planner

```python
import random
from core.studio.slides.types import NARRATIVE_ARC, SLIDE_TYPE_ELEMENTS

def plan_slide_sequence(
    slide_count: int,
    seed: int,
    narrative_arc: list[str] | None = None,
) -> list[dict]:
    """Plan a deterministic slide type sequence based on seed and count.

    Returns a list of dicts with:
      - slide_type: str
      - suggested_elements: list[str]
      - position: str ("opening" | "body" | "closing")

    The sequence follows a narrative arc pattern, stretched or compressed
    to fit the requested slide_count.
    """
    rng = random.Random(seed)
    arc = narrative_arc or NARRATIVE_ARC

    # Stretch or compress the arc to match slide_count
    if slide_count <= len(arc):
        # Sample evenly from arc, always keeping first and last
        indices = [0] + sorted(rng.sample(range(1, len(arc) - 1), slide_count - 2)) + [len(arc) - 1]
        sequence = [arc[i] for i in indices]
    else:
        # Repeat body slides to fill
        sequence = list(arc)
        body_types = ["content", "two_column", "comparison", "timeline", "chart"]
        while len(sequence) < slide_count:
            insert_pos = rng.randint(2, len(sequence) - 2)
            sequence.insert(insert_pos, rng.choice(body_types))

    # Build result with position tags and element suggestions
    result = []
    for i, slide_type in enumerate(sequence):
        if i == 0:
            position = "opening"
        elif i == len(sequence) - 1:
            position = "closing"
        else:
            position = "body"

        result.append({
            "slide_type": slide_type,
            "suggested_elements": SLIDE_TYPE_ELEMENTS.get(slide_type, ["title", "body"]),
            "position": position,
        })

    return result
```

### 5.5 Usage in Orchestrator

The orchestrator calls the generator before the LLM draft call, injecting the planned sequence into the prompt:

```python
# In orchestrator.approve_and_generate_draft() for slides:
seed = compute_seed(artifact_id)  # artifact_id only — Artifact model doesn't store original prompt
count = clamp_slide_count(parameters.get("slide_count"))
sequence = plan_slide_sequence(count, seed)
# sequence is injected as advisory prompt guidance only (see determinism strategy below)
```

> **Determinism strategy (Phase 2):** The planned sequence is injected as prompt guidance only. The LLM may produce a different slide count than planned. Post-generation, `enforce_slide_count()` validates the [8, 15] range on the content tree. Over MAX → trim body slides (preserve opening/closing). Under MIN → pad with filler slides from the planned sequence. Within range → no-op. This ensures the final content tree always meets the slide count contract.

### 5.6 Post-Generation Enforcement

**File:** `core/studio/slides/generator.py`

After LLM generation produces a content tree, `enforce_slide_count()` ensures the slide count is within the [MIN_SLIDES, MAX_SLIDES] range:

```python
def enforce_slide_count(
    content_tree: "SlidesContentTree",
    target_count: int | None = None,
) -> "SlidesContentTree":
    """Enforce [MIN_SLIDES, MAX_SLIDES] range on a content tree.

    - Over MAX_SLIDES: keep first + last slide, trim body from the end
    - Under MIN_SLIDES: insert filler 'content' slides before the closing slide
    - Within range: no-op (returns content_tree unchanged)

    Returns a new SlidesContentTree (does not mutate the input).
    """
    slides = list(content_tree.slides)
    if len(slides) == 0:
        raise ValueError("Cannot enforce slide count on empty slides list")
    target = clamp_slide_count(target_count) if target_count else None

    # Over MAX: trim body slides from the end (preserve first and last)
    if len(slides) > MAX_SLIDES:
        opening = slides[0]
        closing = slides[-1]
        body = slides[1:-1]
        body = body[: MAX_SLIDES - 2]  # Keep first + last = 2 reserved
        slides = [opening] + body + [closing]

    # Under MIN: pad with filler content slides before closing
    if len(slides) < MIN_SLIDES:
        from core.schemas.studio_schema import Slide, SlideElement
        closing = slides[-1]
        body = slides[:-1]
        filler_count = MIN_SLIDES - len(slides)
        for i in range(filler_count):
            filler = Slide(
                id=f"filler-{i+1}",
                slide_type="content",
                title=f"Section {len(body) + 1}",
                elements=[
                    SlideElement(id=f"filler-e-{i+1}", type="body", content="Content to be developed."),
                ],
                speaker_notes="Expand on this section with relevant details.",
            )
            body.append(filler)
        slides = body + [closing]

    # Rebuild content tree with adjusted slides
    return content_tree.model_copy(update={"slides": slides})
```

> **Note:** Filler slides have generic placeholder content. Acceptable for Phase 2; Phase 3 can improve filler quality with context-aware generation.

---

## 6. PPTX Exporter

**File:** `core/studio/slides/exporter.py`

### 6.1 Design Approach

**Programmatic shapes** (not template-based). Each slide type has a dedicated renderer function that places shapes directly via `python-pptx`. This avoids template maintenance burden and gives full control over layout.

### 6.2 Layout Constants

```python
from pptx.util import Inches, Pt, Emu
from pptx.enum.text import PP_ALIGN

# 16:9 widescreen dimensions
SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)

# Margins
MARGIN_LEFT = Inches(0.75)
MARGIN_TOP = Inches(0.75)
MARGIN_RIGHT = Inches(0.75)
MARGIN_BOTTOM = Inches(0.5)

# Content area
CONTENT_WIDTH = SLIDE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
CONTENT_HEIGHT = SLIDE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

# Title area
TITLE_TOP = Inches(0.5)
TITLE_LEFT = MARGIN_LEFT
TITLE_WIDTH = CONTENT_WIDTH
TITLE_HEIGHT = Inches(1.0)

# Body area (below title)
BODY_TOP = Inches(1.8)
BODY_LEFT = MARGIN_LEFT
BODY_WIDTH = CONTENT_WIDTH
BODY_HEIGHT = Inches(5.0)

# Two-column split
COLUMN_GAP = Inches(0.5)
COLUMN_WIDTH = (CONTENT_WIDTH - COLUMN_GAP) / 2
```

### 6.3 Core Export Function

```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pathlib import Path

from core.schemas.studio_schema import SlidesContentTree, SlideTheme

def export_to_pptx(
    content_tree: SlidesContentTree,
    theme: SlideTheme,
    output_path: Path,
) -> Path:
    """Export a SlidesContentTree to PPTX format.

    Uses programmatic shapes (not templates). Each slide type dispatches
    to a dedicated renderer function.

    Returns the output file path.
    """
    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT

    # Use blank layout for all slides (programmatic shapes)
    blank_layout = prs.slide_layouts[6]  # Blank layout

    for slide_data in content_tree.slides:
        pptx_slide = prs.slides.add_slide(blank_layout)

        # Dispatch to type-specific renderer
        renderer = _RENDERERS.get(slide_data.slide_type, _render_content)
        renderer(pptx_slide, slide_data, theme)

        # Add speaker notes
        if slide_data.speaker_notes:
            notes_slide = pptx_slide.notes_slide
            notes_slide.notes_text_frame.text = slide_data.speaker_notes

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))
    return output_path
```

### 6.4 Slide-Type Renderer Functions (10 functions)

Each renderer creates shapes programmatically:

```python
def _render_title(slide, slide_data, theme):
    """Title slide: centered title + subtitle."""
    # Large centered title
    _add_text_box(slide, slide_data.title or "",
                  left=MARGIN_LEFT, top=Inches(2.5),
                  width=CONTENT_WIDTH, height=Inches(1.5),
                  font_name=theme.font_heading, font_size=Pt(44),
                  font_color=theme.colors.primary, alignment=PP_ALIGN.CENTER)
    # Subtitle from elements
    subtitle_el = _find_element(slide_data, "subtitle")
    if subtitle_el and subtitle_el.content:
        _add_text_box(slide, subtitle_el.content,
                      left=MARGIN_LEFT, top=Inches(4.2),
                      width=CONTENT_WIDTH, height=Inches(0.8),
                      font_name=theme.font_body, font_size=Pt(24),
                      font_color=theme.colors.text_light, alignment=PP_ALIGN.CENTER)
    # Background color
    _set_slide_background(slide, theme.colors.background)


def _render_content(slide, slide_data, theme):
    """Standard content slide: title + body/bullets."""
    ...

def _render_two_column(slide, slide_data, theme):
    """Two-column layout: title + left/right body areas."""
    ...

def _render_comparison(slide, slide_data, theme):
    """Comparison slide: title + two labeled columns."""
    ...

def _render_timeline(slide, slide_data, theme):
    """Timeline/roadmap slide: title + sequential items."""
    ...

def _render_chart(slide, slide_data, theme):
    """Chart slide: title + placeholder for chart data."""
    ...

def _render_image_text(slide, slide_data, theme):
    """Image+text slide: split layout with image placeholder and body."""
    ...

def _render_quote(slide, slide_data, theme):
    """Quote slide: large quote text with attribution."""
    ...

def _render_code(slide, slide_data, theme):
    """Code slide: title + monospace code block."""
    ...

def _render_team(slide, slide_data, theme):
    """Team/credits slide: title + team member list."""
    ...


# Renderer dispatch table
_RENDERERS = {
    "title": _render_title,
    "content": _render_content,
    "two_column": _render_two_column,
    "comparison": _render_comparison,
    "timeline": _render_timeline,
    "chart": _render_chart,
    "image_text": _render_image_text,
    "quote": _render_quote,
    "code": _render_code,
    "team": _render_team,
}
```

### 6.5 Helper Functions

```python
def _add_text_box(slide, text, left, top, width, height,
                  font_name="Calibri", font_size=Pt(18),
                  font_color="#000000", alignment=PP_ALIGN.LEFT,
                  bold=False):
    """Add a text box shape with styled text."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = str(text)
    p.font.name = font_name
    p.font.size = font_size
    p.font.bold = bold
    p.alignment = alignment
    if isinstance(font_color, str):
        font_color = RGBColor.from_string(font_color.lstrip("#"))
    p.font.color.rgb = font_color


def _add_bullet_list(slide, items, left, top, width, height,
                     font_name="Calibri", font_size=Pt(16),
                     font_color="#000000"):
    """Add a text box with bullet-point paragraphs."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = f"• {item}"
        p.font.name = font_name
        p.font.size = font_size
        if isinstance(font_color, str):
            p.font.color.rgb = RGBColor.from_string(font_color.lstrip("#"))
        p.space_after = Pt(6)


def _find_element(slide_data, element_type):
    """Find first element of a given type in slide data."""
    for el in slide_data.elements:
        if el.type == element_type:
            return el
    return None


def _set_slide_background(slide, color_hex):
    """Set solid background color for a slide."""
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor.from_string(color_hex.lstrip("#"))
```

---

## 7. PPTX Validator

**File:** `core/studio/slides/validator.py`

### 7.1 Design

Open-validation: reload the exported PPTX file with python-pptx and verify structural integrity. This catches corruption from malformed XML, missing relationships, or invalid slide data.

### 7.2 Implementation

```python
from pathlib import Path
from typing import Dict, Any

def validate_pptx(file_path: Path, expected_slide_count: int | None = None) -> Dict[str, Any]:
    """Validate a PPTX file by reloading and checking structural properties.

    Returns a dict with:
      - valid: bool
      - slide_count: int
      - has_notes: bool (at least one slide has speaker notes)
      - errors: list[str]
    """
    errors = []
    slide_count = 0
    has_notes = False

    try:
        from pptx import Presentation
        prs = Presentation(str(file_path))
        slide_count = len(prs.slides)

        # Check slide count
        if expected_slide_count is not None and slide_count != expected_slide_count:
            errors.append(
                f"Slide count mismatch: expected {expected_slide_count}, got {slide_count}"
            )

        # Check for speaker notes
        for slide in prs.slides:
            try:
                notes_slide = slide.notes_slide
                if notes_slide and notes_slide.notes_text_frame.text.strip():
                    has_notes = True
                    break
            except Exception:
                continue

    except Exception as e:
        errors.append(f"Failed to open PPTX: {str(e)}")

    # Layout-quality heuristic: detect text overflow / unreadable density
    layout_warnings = []
    try:
        from pptx import Presentation as _Prs
        _prs = _Prs(str(file_path))
        BLOCK_CHAR_LIMIT = 800    # Max chars per text block
        SLIDE_CHAR_LIMIT = 1600   # Max total chars per slide
        for slide_idx, slide in enumerate(_prs.slides):
            slide_total = 0
            for shape in slide.shapes:
                if shape.has_text_frame:
                    text_len = len(shape.text_frame.text)
                    slide_total += text_len
                    if text_len > BLOCK_CHAR_LIMIT:
                        layout_warnings.append(
                            f"Slide {slide_idx + 1}: text block exceeds {BLOCK_CHAR_LIMIT} chars ({text_len} chars)"
                        )
            if slide_total > SLIDE_CHAR_LIMIT:
                layout_warnings.append(
                    f"Slide {slide_idx + 1}: total text density exceeds {SLIDE_CHAR_LIMIT} chars ({slide_total} chars)"
                )
    except Exception:
        pass  # Layout check is best-effort; don't fail validation for it

    layout_valid = len(layout_warnings) == 0

    return {
        "valid": len(errors) == 0,
        "slide_count": slide_count,
        "has_notes": has_notes,
        "errors": errors,
        "layout_valid": layout_valid,
        "layout_warnings": layout_warnings,
    }
```

---

## 8. Export Job Lifecycle

### 8.1 Flow

```
POST /api/studio/{artifact_id}/export  {format: "pptx", theme_id: "corporate-blue"}
    |
    v
[1] Load artifact, verify content_tree exists
    |
    v
[2] Resolve theme via get_theme(theme_id)
    |
    v
[3] Create ExportJob (status=pending, generated ID)
    |
    v
[4] Parse content_tree into SlidesContentTree model
    |
    v
[5] Call export_to_pptx(content_tree, theme, output_path)
    |  output_path = studio/{artifact_id}/exports/{export_job_id}.pptx
    |
    v
[6] Run validate_pptx(output_path, expected_slide_count)
    |
    v
[7] Update ExportJob:
    |  - If valid: status=completed, output_uri=path, file_size_bytes, validator_results
    |  - If invalid: status=failed, error=validation_errors
    |
    v
[8] Persist ExportJob JSON to studio/{artifact_id}/exports/{export_job_id}.json
    |
    v
[9] Append export summary to Artifact.exports, save artifact
    |
    v
Return ExportJob payload
```

### 8.2 Export is Synchronous

In Phase 2, export is synchronous (blocking). The PPTX generation for 8-15 slides takes < 1 second, so async queueing is unnecessary. Phase 5 may add async export for large documents if needed.

### 8.3 File Persistence Layout

```
studio/
└── {artifact_id}/
    ├── artifact.json
    ├── revisions/
    │   └── {revision_id}.json
    └── exports/                    # NEW in Phase 2
        ├── {export_job_id}.json    # ExportJob metadata
        └── {export_job_id}.pptx    # Generated file
```

---

## 9. Storage Additions

**File:** `core/studio/storage.py`

### 9.1 New Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `save_export_job` | `(export_job: ExportJob) -> None` | Serialize to `{artifact_id}/exports/{job_id}.json` |
| `load_export_job` | `(artifact_id: str, export_job_id: str) -> Optional[ExportJob]` | Read and parse; return `None` if not found |
| `list_export_jobs` | `(artifact_id: str) -> List[Dict]` | List all export jobs for artifact, sorted by `created_at` desc |
| `get_export_file_path` | `(artifact_id: str, export_job_id: str, format: str) -> Path` | Return path for export file: `{base_dir}/{artifact_id}/exports/{export_job_id}.{format}` |
| `find_export_job` | `(export_job_id: str) -> Optional[Tuple[str, ExportJob]]` | Scan all artifact directories for an export job by ID. Returns `(artifact_id, ExportJob)` or `None`. Used by global export endpoint. |

### 9.2 Implementation Pattern

Follows the exact same pattern as `save_revision()` / `load_revision()` / `list_revisions()`:

```python
def save_export_job(self, export_job: ExportJob) -> None:
    """Save an export job to {artifact_id}/exports/{job_id}.json."""
    exports_dir = self.base_dir / export_job.artifact_id / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    job_file = exports_dir / f"{export_job.id}.json"
    job_file.write_text(json.dumps(export_job.model_dump(mode="json"), indent=2))

def load_export_job(self, artifact_id: str, export_job_id: str) -> Optional["ExportJob"]:
    """Load a specific export job. Returns None if not found."""
    from core.schemas.studio_schema import ExportJob
    job_file = self.base_dir / artifact_id / "exports" / f"{export_job_id}.json"
    if not job_file.exists():
        return None
    data = json.loads(job_file.read_text())
    return ExportJob(**data)

def list_export_jobs(self, artifact_id: str) -> List[Dict]:
    """List all export jobs for an artifact sorted by created_at desc."""
    exports_dir = self.base_dir / artifact_id / "exports"
    if not exports_dir.exists():
        return []
    jobs = []
    for job_file in exports_dir.glob("*.json"):
        try:
            data = json.loads(job_file.read_text())
            jobs.append({
                "id": data.get("id", job_file.stem),
                "format": data.get("format"),
                "status": data.get("status"),
                "created_at": data.get("created_at"),
                "completed_at": data.get("completed_at"),
                "file_size_bytes": data.get("file_size_bytes"),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return sorted(jobs, key=lambda x: x.get("created_at", ""), reverse=True)

def get_export_file_path(self, artifact_id: str, export_job_id: str, fmt: str) -> Path:
    """Return the file path for an exported artifact."""
    return self.base_dir / artifact_id / "exports" / f"{export_job_id}.{fmt}"

def find_export_job(self, export_job_id: str) -> Optional[tuple[str, "ExportJob"]]:
    """Scan all artifact directories for an export job by ID.

    Returns (artifact_id, ExportJob) or None if not found.
    Used by the global GET /studio/exports/{export_job_id} endpoint.
    """
    from core.schemas.studio_schema import ExportJob
    if not self.base_dir.exists():
        return None
    for artifact_dir in self.base_dir.iterdir():
        if not artifact_dir.is_dir():
            continue
        job_file = artifact_dir / "exports" / f"{export_job_id}.json"
        if job_file.exists():
            try:
                data = json.loads(job_file.read_text())
                return (artifact_dir.name, ExportJob(**data))
            except (json.JSONDecodeError, Exception):
                continue
    return None
```

---

## 10. Router Additions

**File:** `routers/studio.py`

### 10.1 New Request Model

```python
class ExportArtifactRequest(BaseModel):
    format: str = "pptx"
    theme_id: Optional[str] = None
```

### 10.1b Path Parameter Validation

All endpoints accepting `artifact_id` as a path parameter must validate it as UUID format before any storage operation. This is defense-in-depth: the server generates UUIDs via `uuid4()`, but the HTTP interface accepts user-supplied strings that could contain path traversal sequences.

```python
import re
from fastapi import HTTPException

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

def _validate_artifact_id(artifact_id: str) -> str:
    """Validate artifact_id is a valid UUID format.

    Raises HTTPException 400 for non-UUID values.
    Called as the first line in every endpoint that accepts artifact_id.
    """
    if not _UUID_PATTERN.match(artifact_id):
        raise HTTPException(status_code=400, detail=f"Invalid artifact_id format: {artifact_id}")
    return artifact_id


def _validate_export_job_id(export_job_id: str) -> str:
    """Validate export_job_id is a valid UUID format.

    Same UUID regex as artifact_id. Prevents path traversal via crafted job IDs.
    Called as the first line in every endpoint that accepts export_job_id.
    """
    if not _UUID_PATTERN.match(export_job_id):
        raise HTTPException(status_code=400, detail=f"Invalid export_job_id format: {export_job_id}")
    return export_job_id
```

**Retrofit:** All existing Phase 1 endpoints (`get_artifact`, `approve_outline`, `list_revisions`, `get_revision`) and all new Phase 2 endpoints must call `_validate_artifact_id(artifact_id)` as their first operation.

### 10.2 New Endpoints (6 total)

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| `POST` | `/studio/{artifact_id}/export` | `export_artifact()` | Start PPTX export; returns export job |
| `GET` | `/studio/{artifact_id}/exports` | `list_exports()` | List all export jobs for an artifact |
| `GET` | `/studio/{artifact_id}/exports/{export_job_id}` | `get_export_job()` | Get a specific export job status |
| `GET` | `/studio/{artifact_id}/exports/{export_job_id}/download` | `download_export()` | Download the exported PPTX file |
| `GET` | `/studio/exports/{export_job_id}` | `get_export_job_global()` | Get export job by ID (global, no artifact_id required) |
| `GET` | `/studio/themes` | `list_themes()` | List all available themes |

### 10.3 Route Ordering Fix

**Critical:** FastAPI matches routes in registration order. The `/studio/themes` GET route must be registered **before** `/studio/{artifact_id}` GET, otherwise `themes` is captured as an `artifact_id` path parameter.

Current order (Phase 1):
```python
@router.get("/{artifact_id}")       # This catches /themes too!
@router.get("")
```

Fixed order (Phase 2):
```python
@router.get("/themes")              # Static path FIRST
@router.get("/exports/{export_job_id}")  # Global export lookup SECOND
@router.get("/{artifact_id}")       # Path param AFTER static paths
@router.get("")
```

> **Note:** `/studio/exports/{export_job_id}` must also be registered before `/{artifact_id}` to prevent `exports` from being captured as an artifact_id.

### 10.4 Export Endpoint Handler

```python
from fastapi.responses import FileResponse
from core.schemas.studio_schema import ExportFormat

@router.post("/{artifact_id}/export")
async def export_artifact(artifact_id: str, request: ExportArtifactRequest):
    """Export an artifact to the specified format."""
    _validate_artifact_id(artifact_id)
    try:
        # Validate format
        try:
            export_format = ExportFormat(request.format)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unsupported export format: {request.format}")

        orchestrator = _get_orchestrator()
        result = await orchestrator.export_artifact(
            artifact_id=artifact_id,
            export_format=export_format,
            theme_id=request.theme_id,
        )
        return result
    except HTTPException:
        raise
    except ValueError as e:
        detail = str(e)
        if "not found" in detail.lower():
            raise HTTPException(status_code=404, detail=detail)
        raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exports/{export_job_id}")
async def get_export_job_global(export_job_id: str):
    """Get an export job by ID without requiring artifact_id.

    Scans all artifact directories for the export job.
    """
    _validate_export_job_id(export_job_id)
    storage = get_studio_storage()
    result = storage.find_export_job(export_job_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Export job not found: {export_job_id}")
    artifact_id, job = result
    return job.model_dump(mode="json")


@router.get("/{artifact_id}/exports/{export_job_id}/download")
async def download_export(artifact_id: str, export_job_id: str):
    """Download an exported file."""
    _validate_artifact_id(artifact_id)
    _validate_export_job_id(export_job_id)
    storage = get_studio_storage()
    job = storage.load_export_job(artifact_id, export_job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Export job not found: {export_job_id}")
    if job.status != ExportStatus.completed:
        raise HTTPException(status_code=400, detail=f"Export job not completed: {job.status}")

    file_path = Path(job.output_uri)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found on disk")

    # Path traversal guard: verify resolved path is under expected exports directory
    expected_base = storage.base_dir / artifact_id / "exports"
    if not file_path.resolve().is_relative_to(expected_base.resolve()):
        raise HTTPException(status_code=400, detail="Export file path outside expected directory")

    return FileResponse(
        path=str(file_path),
        filename=f"{artifact_id}.{job.format.value}",
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
```

### 10.5 Combined Phase 1 + Phase 2 Endpoint Summary

| Method | Path | Phase | Description |
|--------|------|-------|-------------|
| `POST` | `/studio/slides` | 1 | Create slides artifact |
| `POST` | `/studio/documents` | 1 | Create document artifact |
| `POST` | `/studio/sheets` | 1 | Create sheet artifact |
| `POST` | `/studio/{artifact_id}/outline/approve` | 1 | Approve outline |
| `GET`  | `/studio/themes` | **2** | List themes |
| `GET`  | `/studio` | 1 | List all artifacts |
| `GET`  | `/studio/{artifact_id}` | 1 | Get artifact |
| `GET`  | `/studio/{artifact_id}/revisions` | 1 | List revisions |
| `GET`  | `/studio/{artifact_id}/revisions/{revision_id}` | 1 | Get revision |
| `POST` | `/studio/{artifact_id}/export` | **2** | Export artifact |
| `GET`  | `/studio/{artifact_id}/exports` | **2** | List export jobs |
| `GET`  | `/studio/{artifact_id}/exports/{export_job_id}` | **2** | Get export job (artifact-scoped) |
| `GET`  | `/studio/{artifact_id}/exports/{export_job_id}/download` | **2** | Download export |
| `GET`  | `/studio/exports/{export_job_id}` | **2** | Get export job (global) |

**Total: 8 Phase 1 + 6 Phase 2 = 14 endpoints**

---

## 11. Orchestrator Changes

**File:** `core/studio/orchestrator.py`

### 11.1 New Method: `export_artifact()`

```python
async def export_artifact(
    self,
    artifact_id: str,
    export_format: ExportFormat,
    theme_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Export an artifact to the specified format.

    Currently supports PPTX export for slides artifacts.
    Returns the export job dict.
    """
    from core.schemas.studio_schema import ExportJob, ExportStatus, ExportFormat
    from core.studio.slides.themes import get_theme
    from core.studio.slides.exporter import export_to_pptx
    from core.studio.slides.validator import validate_pptx
    from core.schemas.studio_schema import SlidesContentTree

    # Load and verify artifact
    artifact = self.storage.load_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"Artifact not found: {artifact_id}")
    if artifact.content_tree is None:
        raise ValueError(f"Artifact {artifact_id} has no content tree (approve outline first)")
    if artifact.type != ArtifactType.slides:
        raise ValueError(f"Export format {export_format.value} only supports slides artifacts")

    # Resolve theme
    theme = get_theme(theme_id or artifact.theme_id)

    # Create export job
    now = datetime.now(timezone.utc)
    export_job_id = str(uuid4())
    export_job = ExportJob(
        id=export_job_id,
        artifact_id=artifact_id,
        format=export_format,
        status=ExportStatus.pending,
        created_at=now,
    )

    # Persist as "pending" immediately so the job is visible even if export fails
    self.storage.save_export_job(export_job)

    try:
        # Parse content tree
        content_tree_model = SlidesContentTree(**artifact.content_tree)

        # Export to PPTX
        output_path = self.storage.get_export_file_path(
            artifact_id, export_job_id, export_format.value
        )
        export_to_pptx(content_tree_model, theme, output_path)

        # Validate
        validation = validate_pptx(output_path, expected_slide_count=len(content_tree_model.slides))

        if validation["valid"]:
            export_job.status = ExportStatus.completed
            export_job.output_uri = str(output_path)
            export_job.file_size_bytes = output_path.stat().st_size
            export_job.validator_results = validation
            export_job.completed_at = datetime.now(timezone.utc)
        else:
            export_job.status = ExportStatus.failed
            export_job.error = "; ".join(validation["errors"])
            export_job.validator_results = validation
            export_job.completed_at = datetime.now(timezone.utc)

    except Exception as e:
        export_job.status = ExportStatus.failed
        export_job.error = str(e)
        export_job.completed_at = datetime.now(timezone.utc)

    # Persist export job
    self.storage.save_export_job(export_job)

    # Update artifact exports summary (typed ExportJobSummary)
    from core.schemas.studio_schema import ExportJobSummary
    artifact.exports.append(ExportJobSummary(
        id=export_job.id,
        format=export_job.format.value,
        status=export_job.status.value,
        created_at=export_job.created_at,
    ))
    artifact.updated_at = datetime.now(timezone.utc)
    self.storage.save_artifact(artifact)

    return export_job.model_dump(mode="json")
```

### 11.2 Changes to Existing Methods

`generate_outline()` remains unchanged. `approve_and_generate_draft()` gets two slides-only hooks:

1. **Pre-LLM:** Compute and inject deterministic sequence hints into the draft prompt via `compute_seed()` + `plan_slide_sequence()`.
2. **Post-LLM:** After LLM generation and content tree parsing, call `enforce_slide_count(content_tree, target_count)` to ensure the [8, 15] range is met before saving the content tree.

`export_artifact()` is a new method that operates on already-drafted artifacts.

---

## 12. Prompt Improvements

**File:** `core/studio/prompts.py`

### 12.1 Enhanced Slides Outline Guidance

Update `_get_type_specific_outline_guidance()` for slides to include:

```python
if artifact_type == ArtifactType.slides:
    return """Guidance for slides:
- Plan a narrative arc: opening hook, problem statement, solution overview, evidence/data, call to action
- Each outline item represents one slide
- Suggest 8-12 slides unless the user specifies a count
- Include speaker notes suggestions in descriptions — these become presenter notes in the exported PPTX
- Consider slide types and pick the best fit for each slide's content:
  * title — Opening/closing slides with large centered text
  * content — Standard slide with title + body paragraphs or bullet points
  * two_column — Side-by-side comparison or complementary content
  * comparison — Explicit pros/cons or before/after layout
  * timeline — Sequential steps, milestones, or roadmap
  * chart — Data visualization with supporting context
  * image_text — Split layout with image area and descriptive text
  * quote — Featured quotation with attribution
  * code — Technical slide with monospace code block
  * team — Team members, credits, or acknowledgments
- Assign a slide_type to each item in the description field (e.g., "slide_type: two_column")"""
```

### 12.2 Enhanced Slides Draft Schema

Update `_get_type_specific_draft_schema()` for slides to include explicit speaker notes guidance:

```python
# Add to the existing slides draft prompt:
"""
- speaker_notes are REQUIRED for every slide — write 2-3 sentences of presenter guidance
- Speaker notes should provide talking points, not repeat slide content
- For bullet_list elements, content must be a JSON array of strings
- Match the slide_type to the content purpose:
  * Use "title" for opening and closing slides
  * Use "content" for main narrative slides
  * Use "two_column" when comparing or contrasting
  * Use "quote" for testimonials or key insights
  * Use "chart" when referencing data or metrics
"""
```

### 12.3 Slide Sequence Hints in Draft Prompt

When the deterministic generator has planned a sequence, inject it into the draft prompt:

```python
def get_draft_prompt_with_sequence(
    artifact_type: ArtifactType,
    outline: Outline,
    slide_sequence: list[dict] | None = None,
) -> str:
    """Enhanced draft prompt that includes planned slide sequence."""
    base_prompt = get_draft_prompt(artifact_type, outline)

    if slide_sequence and artifact_type == ArtifactType.slides:
        sequence_hint = "\n\nPlanned slide sequence (follow this structure):\n"
        for i, s in enumerate(slide_sequence, 1):
            sequence_hint += f"  Slide {i}: type={s['slide_type']}, position={s['position']}\n"
        base_prompt += sequence_hint

    return base_prompt
```

---

## 13. Dependencies

**File:** `pyproject.toml`

Add `python-pptx` to the dependencies list:

```toml
dependencies = [
    ...
    "python-pptx>=1.0.2",
    ...
]
```

After adding, run:
```bash
uv sync --python 3.11
```

No other new dependencies required. `hashlib` and `random` are stdlib modules used by the generator.

---

## 14. Test Plan

Tests are organized into **unit tests** (model/logic correctness), **component tests** (exporter/validator behavior), **router tests** (HTTP endpoint wiring), **acceptance tests** (P04 gate criteria), and **integration tests** (cross-component flows). All files follow the flat `tests/test_*.py` convention per CLAUDE.md.

### `tests/test_studio_slides_types.py` — 8 tests

| Test | What It Verifies |
|------|-----------------|
| `test_all_slide_types_defined` | `SLIDE_TYPES` contains exactly 10 types |
| `test_all_element_types_defined` | `ELEMENT_TYPES` contains exactly 8 types |
| `test_slide_type_elements_complete` | Every slide type in `SLIDE_TYPES` has an entry in `SLIDE_TYPE_ELEMENTS` |
| `test_element_types_in_mapping_are_valid` | Every element type referenced in `SLIDE_TYPE_ELEMENTS` is in `ELEMENT_TYPES` |
| `test_is_valid_slide_type` | `is_valid_slide_type()` returns True/False correctly |
| `test_is_valid_element_type` | `is_valid_element_type()` returns True/False correctly |
| `test_get_elements_for_slide_type_known` | Returns correct elements for "title" |
| `test_get_elements_for_slide_type_unknown` | Returns fallback `["title", "body"]` for unknown type |

### `tests/test_studio_slides_themes.py` — 10+ tests

| Test | What It Verifies |
|------|-----------------|
| `test_all_themes_load` | All 8 themes are loadable via `list_themes()` |
| `test_get_theme_by_id` | `get_theme("corporate-blue")` returns correct theme |
| `test_get_theme_default` | `get_theme()` with no args returns corporate-blue |
| `test_get_theme_unknown_falls_back` | `get_theme("nonexistent")` returns corporate-blue |
| `test_get_theme_none_falls_back` | `get_theme(None)` returns corporate-blue |
| `test_theme_has_required_colors` | Every theme has all 6 color fields populated |
| `test_theme_colors_are_hex` | All color values match `#[0-9A-Fa-f]{6}` pattern |
| `test_theme_has_fonts` | Every theme has non-empty `font_heading` and `font_body` |
| `test_theme_ids_are_unique` | No duplicate theme IDs |
| `test_get_theme_ids` | `get_theme_ids()` returns list of all theme IDs |
| `test_theme_roundtrip_serialization` | `SlideTheme(**theme.model_dump()) == theme` for all themes |

### `tests/test_studio_slides_generator.py` — 17 tests

| Test | What It Verifies |
|------|-----------------|
| `test_compute_seed_deterministic` | Same inputs always produce same seed |
| `test_compute_seed_different_inputs` | Different inputs produce different seeds |
| `test_clamp_slide_count_default` | `clamp_slide_count(None)` returns 10 |
| `test_clamp_slide_count_within_range` | `clamp_slide_count(12)` returns 12 |
| `test_clamp_slide_count_below_min` | `clamp_slide_count(3)` returns 8 |
| `test_clamp_slide_count_above_max` | `clamp_slide_count(50)` returns 15 |
| `test_plan_slide_sequence_count` | Output length matches requested slide count |
| `test_plan_slide_sequence_deterministic` | Same seed produces same sequence |
| `test_plan_slide_sequence_different_seeds` | Different seeds produce different sequences |
| `test_plan_slide_sequence_opens_with_title` | First slide is always "title" type |
| `test_plan_slide_sequence_closes_with_title` | Last slide is always "title" type |
| `test_plan_slide_sequence_positions` | First has "opening", last has "closing", rest have "body" |
| `test_plan_slide_sequence_all_types_valid` | All slide types in output are in `SLIDE_TYPES` |
| `test_enforce_slide_count_over_max` | 20 slides → trimmed to 15, preserving first and last |
| `test_enforce_slide_count_under_min` | 5 slides → padded to 8 with filler content slides |
| `test_enforce_slide_count_preserves_opening_closing` | First and last slides preserved after trim/pad |
| `test_enforce_slide_count_within_range_no_change` | 10 slides → unchanged (no-op) |

### `tests/test_studio_slides_exporter.py` — 14 tests

All tests use `tmp_path` pytest fixture for output isolation.

| Test | What It Verifies |
|------|-----------------|
| `test_export_creates_file` | `export_to_pptx()` creates a `.pptx` file at output_path |
| `test_export_slide_count` | Exported PPTX has correct number of slides |
| `test_export_speaker_notes_present` | At least one slide has speaker notes |
| `test_export_all_slides_have_notes` | Every slide with `speaker_notes` has notes in PPTX |
| `test_export_slide_dimensions` | Slide width/height match 16:9 widescreen constants |
| `test_export_title_slide_rendering` | Title slide has text content matching input |
| `test_export_content_slide_rendering` | Content slide has title and body text |
| `test_export_two_column_rendering` | Two-column slide has shapes for both columns |
| `test_export_quote_slide_rendering` | Quote slide renders quote content |
| `test_export_code_slide_rendering` | Code slide renders with monospace styling |
| `test_export_with_different_themes` | Same content with different themes produces valid PPTX |
| `test_export_rejects_empty_slides_list` | Empty slides list returns a controlled validation error |
| `test_export_output_directory_created` | Missing parent directories are created |
| `test_export_unknown_slide_type_fallback` | Unknown slide_type falls back to `_render_content` without error |

**Test fixture pattern:**

```python
import pytest
from pathlib import Path
from core.schemas.studio_schema import SlidesContentTree, Slide, SlideElement
from core.studio.slides.themes import get_theme
from core.studio.slides.exporter import export_to_pptx

@pytest.fixture
def sample_content_tree():
    return SlidesContentTree(
        deck_title="Test Deck",
        subtitle="Test Subtitle",
        slides=[
            Slide(
                id="s1",
                slide_type="title",
                title="Welcome",
                elements=[
                    SlideElement(id="e1", type="title", content="Welcome"),
                    SlideElement(id="e2", type="subtitle", content="A test deck"),
                ],
                speaker_notes="Open with a greeting.",
            ),
            Slide(
                id="s2",
                slide_type="content",
                title="Agenda",
                elements=[
                    SlideElement(id="e3", type="title", content="Agenda"),
                    SlideElement(id="e4", type="bullet_list", content=["Item 1", "Item 2", "Item 3"]),
                ],
                speaker_notes="Walk through the agenda items.",
            ),
        ],
    )

@pytest.fixture
def default_theme():
    return get_theme()
```

### `tests/test_studio_export_router.py` — 11 tests

Uses monkeypatch to mock `_get_orchestrator()` (same pattern as `test_studio_router.py`).

| Test | What It Verifies |
|------|-----------------|
| `test_export_artifact_success` | `POST /studio/{id}/export` with valid format returns export job |
| `test_export_artifact_invalid_format` | `POST /studio/{id}/export` with `format: "pdf"` returns 400 |
| `test_export_artifact_not_found` | `POST /studio/missing/export` returns 404 |
| `test_list_exports_success` | `GET /studio/{id}/exports` returns list of export jobs |
| `test_get_export_job_success` | `GET /studio/{id}/exports/{job_id}` returns job details |
| `test_get_export_job_not_found` | `GET /studio/{id}/exports/missing` returns 404 |
| `test_download_export_success` | `GET /studio/{id}/exports/{job_id}/download` returns FileResponse |
| `test_list_themes` | `GET /studio/themes` returns list of 8 themes |
| `test_export_artifact_invalid_artifact_id` | `POST /studio/../etc/passwd/export` returns 400 (path traversal) |
| `test_get_artifact_invalid_id_format` | `GET /studio/not-a-uuid` returns 400 (non-UUID format) |
| `test_get_export_job_global` | `GET /studio/exports/{job_id}` returns export job without artifact_id in path |

### Updated Acceptance Tests — `tests/acceptance/p04_forge/test_exports_open_and_render.py`

Keep existing 8 scaffold tests (test_01 through test_08). Add 9 new functional tests:

| Test | What It Verifies |
|------|-----------------|
| `test_09_slides_content_tree_validates` | A sample SlidesContentTree passes Pydantic validation |
| `test_10_pptx_export_produces_file` | `export_to_pptx()` creates a valid PPTX file |
| `test_11_pptx_open_validation_passes` | `validate_pptx()` confirms the exported file opens cleanly |
| `test_12_slide_count_in_range` | Exported deck has 8-15 slides (when using clamp_slide_count) |
| `test_13_speaker_notes_present_in_export` | At least one slide has speaker notes in the PPTX |
| `test_14_export_job_status_completed` | Export job ends with `status=completed` for valid input |
| `test_15_invalid_format_returns_error` | Requesting unsupported format returns controlled error |
| `test_16_export_job_has_validator_results` | Export job includes validator_results (`valid`, `slide_count`, `has_notes`, `errors`) |
| `test_17_layout_validator_detects_overflow` | Slide with 2000+ chars triggers `layout_valid=False` in validator results (non-blocking warning) |

**Integration test mocking strategy:** Integration tests that call `approve_and_generate_draft()` must monkeypatch `ModelManager.generate_text` to return deterministic fixture JSON. This avoids external LLM dependency and CI flakiness. The monkeypatch returns a valid `SlidesContentTree` JSON string matching the sample fixture in the exporter tests. This is consistent with Phase 1 router tests that mock `_get_orchestrator()`.

### Updated Integration Tests — `tests/integration/test_forge_research_to_slides.py`

Keep existing 5 scaffold tests (test_01 through test_05). Add 8 new functional tests:

| Test | What It Verifies |
|------|-----------------|
| `test_06_outline_to_draft_to_export_pipeline` | Full pipeline: create outline → approve → export PPTX |
| `test_07_export_with_custom_theme` | Export with non-default theme produces valid PPTX |
| `test_08_export_preserves_revision_lineage` | Revision head_id unchanged after export |
| `test_09_multiple_exports_tracked` | Two exports for same artifact both appear in exports list |
| `test_10_export_file_downloadable` | Export file path exists and has non-zero size |
| `test_11_oracle_research_ingestion` | Monkeypatch Oracle MCP call with fixture (2-3 source entries: title, URL, snippet); verify research content appears in content tree |
| `test_12_canvas_preview_no_schema_breakage` | Round-trip content tree through Canvas surface state; verify `validate_content_tree()` passes |
| `test_13_upstream_failure_graceful_downstream` | Monkeypatch `ModelManager.generate_text` to raise `RuntimeError("LLM unavailable")`; verify HTTP 500 with meaningful error, artifact state intact, failure logged |

**Cross-project mocking strategy:** Oracle test uses a fixture with 2-3 source entries (title, URL, snippet) injected via monkeypatch on the Oracle MCP call. Failure test raises `RuntimeError("LLM unavailable")` from `generate_text` and verifies the artifact remains in its pre-failure state.

### Test Count Summary

| Test File | Count | Category |
|-----------|-------|----------|
| `test_studio_slides_types.py` | 8 | Unit |
| `test_studio_slides_themes.py` | 11 | Unit |
| `test_studio_slides_generator.py` | 17 | Unit |
| `test_studio_slides_exporter.py` | 14 | Component |
| `test_studio_export_router.py` | 11 | Router |
| `test_exports_open_and_render.py` (new tests) | 9 | Acceptance |
| `test_forge_research_to_slides.py` (new tests) | 8 | Integration |
| **Total new tests** | **78** | |
| Existing Phase 1 tests (unchanged) | 65+ | |
| **Combined total** | **143+** | |

---

## 15. Day-by-Day Execution Sequence

### Day 6: Slides Generator + Theme Catalog

1. Add `python-pptx>=1.0.2` to `pyproject.toml`, run `uv sync --python 3.11`
2. Add schema models to `core/schemas/studio_schema.py`: `ExportFormat`, `ExportStatus`, `ExportJob`, `SlideThemeColors`, `SlideTheme`, `Artifact.exports` field
3. Create `core/studio/slides/__init__.py` (empty)
4. Create `core/studio/slides/types.py` — slide type constants, element types, narrative arc, helpers
5. Create `core/studio/slides/themes.py` — 8 curated themes, `get_theme()`, `list_themes()`
6. Create `core/studio/slides/generator.py` — `compute_seed()`, `clamp_slide_count()`, `plan_slide_sequence()`
7. Create `tests/test_studio_slides_types.py` (8 tests)
8. Create `tests/test_studio_slides_themes.py` (11 tests)
9. Create `tests/test_studio_slides_generator.py` (17 tests)
10. Run: `python -m pytest tests/test_studio_slides_types.py tests/test_studio_slides_themes.py tests/test_studio_slides_generator.py -q`

**Exit gate:** All 36 new tests pass (8 + 11 + 17). Schema backward compatibility verified (existing schema tests still pass).

### Day 7: PPTX Exporter + Export Pipeline

1. Create `core/studio/slides/exporter.py` — 10 renderer functions + `export_to_pptx()`
2. Create `core/studio/slides/validator.py` — `validate_pptx()`
3. Modify `core/studio/storage.py` — add `save_export_job()`, `load_export_job()`, `list_export_jobs()`, `get_export_file_path()`
4. Modify `core/studio/orchestrator.py` — add `export_artifact()` method
5. Modify `core/studio/prompts.py` — enhance slides prompts with speaker notes guidance, slide type descriptions, sequence hints
6. Create `tests/test_studio_slides_exporter.py` (14 tests)
7. Run: `python -m pytest tests/test_studio_slides_exporter.py -q`
8. Verify PPTX output opens in a viewer (manual spot-check)

**Exit gate:** All exporter tests pass. Generated PPTX opens without corruption. Speaker notes present.

### Day 8: Router + Full Test Suite + Polish

1. Modify `routers/studio.py` — add 6 new endpoints, fix route ordering (`/themes` before `/{artifact_id}`)
2. Create `tests/test_studio_export_router.py` (11 tests)
3. Update `tests/acceptance/p04_forge/test_exports_open_and_render.py` — add 9 functional tests
4. Update `tests/integration/test_forge_research_to_slides.py` — add 8 functional tests (5 pipeline + 3 cross-project)
5. Run full suite: `python -m pytest tests/test_studio_*.py tests/test_studio_slides_*.py -v`
6. Run baseline: `scripts/test_all.sh quick` — ensure no regressions
7. Run P04 acceptance: `python -m pytest tests/acceptance/p04_forge/ -v`
8. Run P04 integration: `python -m pytest tests/integration/test_forge_research_to_slides.py -v`
9. Manual E2E test:

```bash
# Start server
uv run api.py

# Create slides with outline
curl -X POST http://localhost:8000/api/studio/slides \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Create a 10-slide pitch deck for an AI startup"}'

# Approve outline (use artifact_id from response)
curl -X POST http://localhost:8000/api/studio/{artifact_id}/outline/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'

# Export to PPTX
curl -X POST http://localhost:8000/api/studio/{artifact_id}/export \
  -H "Content-Type: application/json" \
  -d '{"format": "pptx", "theme_id": "tech-dark"}'

# List available themes
curl http://localhost:8000/api/studio/themes

# Download the PPTX (use export_job_id from response)
curl -o output.pptx http://localhost:8000/api/studio/{artifact_id}/exports/{export_job_id}/download

# Verify the file opens
open output.pptx
```

10. Verify all Phase 2 exit criteria (table below)

**Exit gate:** All tests green. Full pipeline works end-to-end. PPTX opens in viewer.

---

## 16. Exit Criteria

| # | Criterion | How to Verify |
|---|-----------|---------------|
| 1 | Slide type registry has 10 types and 8 element types | `test_studio_slides_types.py` |
| 2 | All 8 curated themes load and validate | `test_studio_slides_themes.py` |
| 3 | Unknown theme ID falls back to corporate-blue | `test_studio_slides_themes.py::test_get_theme_unknown_falls_back` |
| 4 | `clamp_slide_count()` + `enforce_slide_count()` enforce [8, 15] range end-to-end (prompt hint + post-generation trim/pad) | `test_studio_slides_generator.py` |
| 5 | `plan_slide_sequence()` is deterministic with same seed | `test_studio_slides_generator.py::test_plan_slide_sequence_deterministic` |
| 6 | PPTX export creates valid file | `test_studio_slides_exporter.py::test_export_creates_file` |
| 7 | Speaker notes present in exported PPTX | `test_studio_slides_exporter.py::test_export_speaker_notes_present` |
| 8 | Exported PPTX passes open-validation | `test_exports_open_and_render.py::test_11_pptx_open_validation_passes` |
| 9 | Export job tracks status correctly (pending → completed/failed) | `test_studio_export_router.py::test_export_artifact_success` |
| 10 | Export file downloadable via API | `test_studio_export_router.py::test_download_export_success` |
| 11 | `/themes` endpoint returns all 8 themes | `test_studio_export_router.py::test_list_themes` |
| 12 | Existing Phase 1 artifacts without `exports` field load correctly | Backward compat: `test_studio_schema.py` + `test_studio_storage.py` |
| 13 | No regressions in existing tests | `scripts/test_all.sh quick` passes |
| 14 | P04 acceptance and integration gates green | `pytest tests/acceptance/p04_forge/ tests/integration/test_forge_research_to_slides.py -v` |
| 15 | Layout-quality validator **detects** overflow/unreadable slides (non-blocking warning; Phase 3 may promote to blocking) | `test_exports_open_and_render.py::test_17_layout_validator_detects_overflow` |

---

## 17. Risks & Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| 1 | python-pptx generates corrupt XML for edge-case slide content | Medium | High | Open-validation catches corruption. Exporter uses simple shapes (no complex SmartArt or OLE). Validator tests cover all 10 slide types. |
| 2 | Font names in themes not available on export machine | Low | Low | python-pptx embeds font name references, not font files. Missing fonts degrade to system defaults in the viewer. Not a corruption issue. |
| 3 | LLM ignores slide sequence hints in prompt | Medium | Medium | Structural determinism is enforced by the generator (slide count, type sequence). LLM fills content only. If LLM produces different slide types, the exporter falls back to `_render_content` for unknown types. |
| 4 | Backward compatibility: existing artifacts missing `exports` field | Low | Medium | `exports: List[Dict] = Field(default_factory=list)` means missing field deserializes as `[]`. Verified by existing schema round-trip tests. |
| 5 | `/themes` route captured by `/{artifact_id}` path parameter | High | High | Fix route ordering: register `/themes` before `/{artifact_id}`. Explicit test in `test_studio_export_router.py`. |
| 6 | Large PPTX files slow down synchronous export | Low | Low | 8-15 slides with text-only shapes produce < 100KB files. Generation takes < 1 second. Async export deferred to Phase 5 if needed. |
| 7 | Export file path traversal via crafted artifact_id | Low | High | `artifact_id` validated as UUID format by `_validate_artifact_id()` before any storage operation. Defense-in-depth: server generates UUIDs, but the HTTP interface accepts user-supplied strings. |
| 8 | python-pptx version incompatibility | Low | Medium | Pin `>=1.0.2` (current stable). python-pptx has stable API for shape creation and notes. No alpha/beta features used. |

---

## 18. Phase 3 Extension Hooks

Phase 2 is designed with explicit extension points for Phase 3 (Days 9-10: Quality + Polish):

| Hook | Where | What Phase 3 Adds |
|------|-------|------------------|
| `SlideTheme` model | `studio_schema.py` | Add `variant_seed: Optional[int]`, `gradient_stops: Optional[List]` for procedural theme variants |
| `_THEMES` registry | `themes.py` | Add `generate_theme_variant(base_id, seed)` for procedural generation of 100+ variants |
| `_RENDERERS` dispatch | `exporter.py` | Add chart rendering (matplotlib → image → slide) for `_render_chart()` |
| `validate_pptx()` | `validator.py` | Enhance beyond text-length heuristic: pixel-level overflow, whitespace balance, font consistency |
| `NARRATIVE_ARC` | `types.py` | Add audience-specific arc patterns (technical, executive, educational) |
| `ExportFormat` enum | `studio_schema.py` | Add `pdf`, `html`, `google_slides` values for Phase 4-5 |
| `export_artifact()` | `orchestrator.py` | Add format dispatch for document/sheet exports |
| Draft prompt | `prompts.py` | Add image placeholder descriptions, chart data specifications |

---

## Appendix A: Key Existing Files Referenced

| File | Lines | What It Provides |
|------|-------|-----------------|
| `core/schemas/studio_schema.py` | 1-172 | All Phase 1 Pydantic models: Artifact, Revision, Outline, content trees, validation helpers |
| `core/studio/orchestrator.py` | 1-196 | `ForgeOrchestrator` with `generate_outline()`, `approve_and_generate_draft()`, `reject_outline()` |
| `core/studio/storage.py` | 1-117 | `StudioStorage` with artifact + revision CRUD methods |
| `core/studio/revision.py` | 1-70 | `RevisionManager` + `compute_change_summary()` |
| `core/studio/prompts.py` | 1-183 | `get_outline_prompt()`, `get_draft_prompt()`, type-specific guidance |
| `routers/studio.py` | 1-150 | Phase 1 router with 8 endpoints, request models, error handling |
| `shared/state.py` | ~70 | `get_studio_storage()` lazy singleton |
| `pyproject.toml` | 1-40 | Current dependencies (no python-pptx yet) |

## Appendix B: Content Tree JSON Example (Slides with Theme)

```json
{
  "deck_title": "Series A Pitch Deck",
  "subtitle": "Acme AI — Transforming Enterprise Automation",
  "slides": [
    {
      "id": "s1",
      "slide_type": "title",
      "title": "Acme AI",
      "elements": [
        {"id": "e1", "type": "title", "content": "Acme AI"},
        {"id": "e2", "type": "subtitle", "content": "Series A Pitch Deck — 2026"}
      ],
      "speaker_notes": "Welcome the audience. Introduce yourself and the company mission."
    },
    {
      "id": "s2",
      "slide_type": "content",
      "title": "The Problem",
      "elements": [
        {"id": "e3", "type": "body", "content": "Enterprises waste 40% of operational time on manual, repetitive processes."},
        {"id": "e4", "type": "bullet_list", "content": ["Manual data entry across 5+ systems", "Fragmented tooling with no integration", "No real-time visibility into operations"]}
      ],
      "speaker_notes": "Emphasize the pain points. Use the 40% statistic as the hook."
    },
    {
      "id": "s3",
      "slide_type": "two_column",
      "title": "Before vs After",
      "elements": [
        {"id": "e5", "type": "body", "content": "Before: Manual processes, siloed data, reactive decisions."},
        {"id": "e6", "type": "body", "content": "After: Automated workflows, unified data, proactive intelligence."}
      ],
      "speaker_notes": "Walk through the transformation story. Let the audience see themselves in the 'before' column."
    }
  ],
  "metadata": {"audience": "investors", "tone": "professional", "theme_id": "corporate-blue"}
}
```

## Appendix C: Export Job JSON Example

```json
{
  "id": "exp-a1b2c3d4",
  "artifact_id": "art-e5f6g7h8",
  "format": "pptx",
  "status": "completed",
  "output_uri": "studio/art-e5f6g7h8/exports/exp-a1b2c3d4.pptx",
  "file_size_bytes": 87432,
  "validator_results": {
    "valid": true,
    "slide_count": 10,
    "has_notes": true,
    "errors": []
  },
  "created_at": "2026-02-21T10:30:00Z",
  "completed_at": "2026-02-21T10:30:01Z",
  "error": null
}
```
