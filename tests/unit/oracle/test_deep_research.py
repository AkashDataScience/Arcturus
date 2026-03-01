"""Unit tests for the deep research (Oracle) pipeline.

Covers: focus_modes, synthesizer helpers, query_decomposer,
crawl_pipeline, DeepResearchEvent, cache, and graph_bridge.
"""
import asyncio
import json
import textwrap
from dataclasses import asdict
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

# ── Module imports ──
from search.focus_modes import (
    FocusConfig,
    apply_focus,
    get_focus_config,
    list_focus_modes,
)
from search.synthesizer import (
    Citation,
    SynthesisResult,
    _build_sources_block,
    _parse_synthesis,
)
from search.deep_research import DeepResearchEvent
from search.crawl_pipeline import SourceDocument


# =====================================================================
# 1. Focus Modes  (3 tests)
# =====================================================================


def test_get_focus_config_known_mode():
    """get_focus_config('academic') returns correct config with APA citations."""
    cfg = get_focus_config("academic")
    assert isinstance(cfg, FocusConfig)
    assert cfg.name == "academic"
    assert cfg.citation_format == "apa"
    assert "arxiv.org" in cfg.search_suffix


def test_get_focus_config_unknown_defaults_to_web():
    """Unknown mode falls back to 'web' config."""
    cfg = get_focus_config("nonexistent_mode")
    assert cfg.name == "web"
    assert cfg.search_suffix == ""


def test_apply_focus_appends_suffix():
    """apply_focus adds the mode suffix; 'web' leaves queries unchanged."""
    queries = ["query one", "query two"]

    # Code mode should append suffix
    enriched = apply_focus(queries, "code")
    for q in enriched:
        assert "site:github.com" in q

    # Web mode has no suffix — queries returned unchanged
    unchanged = apply_focus(queries, "web")
    assert unchanged == queries


# =====================================================================
# 2. Synthesizer helpers  (3 tests)
# =====================================================================

SAMPLE_SOURCES = [
    {"url": "https://example.com/1", "title": "Source One", "content": "Alpha content"},
    {"url": "https://example.com/2", "title": "Source Two", "content": "Beta content"},
]


def test_build_sources_block_formatting():
    """_build_sources_block produces numbered [N] URL/Title/Content blocks."""
    block = _build_sources_block(SAMPLE_SOURCES)
    assert "[1] URL: https://example.com/1" in block
    assert "[2] URL: https://example.com/2" in block
    assert "Title: Source One" in block
    assert "Content: Alpha content" in block


def test_build_sources_block_truncates_content():
    """Content longer than 6000 chars is truncated."""
    long_source = [{"url": "https://x.com", "title": "T", "content": "A" * 10000}]
    block = _build_sources_block(long_source)
    # The content portion should be at most 6000 chars
    content_line = [line for line in block.split("\n") if "Content:" in line][0]
    content_text = content_line.split("Content: ", 1)[1]
    assert len(content_text) == 6000


def test_parse_synthesis_with_json_block():
    """_parse_synthesis extracts markdown + structured JSON block correctly."""
    raw = textwrap.dedent("""\
        # Research Report

        The findings show X [1] and Y [2].

        ```json
        {
            "executive_summary": "Summary of research.",
            "citations": [
                {"index": 1, "url": "https://example.com/1", "title": "Source One", "credibility": "HIGH"},
                {"index": 2, "url": "https://example.com/2", "title": "Source Two", "credibility": "MEDIUM"}
            ],
            "confidence_per_para": ["HIGH"],
            "contradictions": ["Source 1 claims X while Source 2 states Y"]
        }
        ```
    """)
    result = _parse_synthesis(raw, SAMPLE_SOURCES)

    assert isinstance(result, SynthesisResult)
    assert "Research Report" in result.answer_md
    assert result.executive_summary == "Summary of research."
    assert len(result.citations) == 2
    assert result.citations[0].credibility == "HIGH"
    assert len(result.contradictions) == 1


def test_parse_synthesis_fallback_no_json():
    """Without a JSON block, citations are built from the source list."""
    raw = "# Report\n\nSome answer text without any JSON block."
    result = _parse_synthesis(raw, SAMPLE_SOURCES)

    assert result.answer_md == raw
    assert len(result.citations) == len(SAMPLE_SOURCES)
    assert result.citations[0].url == "https://example.com/1"
    assert result.executive_summary == ""


# =====================================================================
# 3. Query Decomposer  (2 tests)
# =====================================================================


@patch("search.query_decomposer._get_gemini_client")
def test_decompose_parses_json_array(mock_get_client):
    """decompose() parses a clean JSON array from the LLM and applies focus."""
    from search.query_decomposer import decompose

    mock_client = MagicMock()
    mock_client.generate_text = AsyncMock(
        return_value='["sub query 1", "sub query 2", "sub query 3"]'
    )
    mock_get_client.return_value = mock_client

    result = asyncio.run(decompose("test query", focus_mode="web", n_queries=3))

    assert len(result) == 3
    assert result[0] == "sub query 1"  # web mode has no suffix


@patch("search.query_decomposer._get_gemini_client")
def test_decompose_fallback_on_bad_json(mock_get_client):
    """decompose() falls back to line-splitting when LLM returns non-JSON."""
    from search.query_decomposer import decompose

    mock_client = MagicMock()
    mock_client.generate_text = AsyncMock(
        return_value="- first sub query\n- second sub query\n- third sub query"
    )
    mock_get_client.return_value = mock_client

    result = asyncio.run(decompose("test query", focus_mode="web", n_queries=6))

    assert len(result) >= 3
    assert "first sub query" in result[0]


# =====================================================================
# 4. Crawl Pipeline  (2 tests)
# =====================================================================


@patch("search.crawl_pipeline.smart_web_extract", new_callable=AsyncMock)
def test_extract_single_success(mock_extract):
    """_extract_single returns a SourceDocument with content on success."""
    from search.crawl_pipeline import _extract_single

    mock_extract.return_value = {
        "best_text": "Extracted page content here.",
        "title": "Page Title",
    }

    doc = asyncio.run(_extract_single("https://example.com", rank=1))

    assert isinstance(doc, SourceDocument)
    assert doc.error is None
    assert doc.title == "Page Title"
    assert "Extracted page content" in doc.content
    assert doc.rank == 1


@patch("search.crawl_pipeline.smart_web_extract", new_callable=AsyncMock)
def test_extract_single_timeout(mock_extract):
    """_extract_single returns a SourceDocument with error on timeout."""
    from search.crawl_pipeline import _extract_single

    mock_extract.side_effect = asyncio.TimeoutError()

    doc = asyncio.run(_extract_single("https://slow-site.com", rank=5))

    assert doc.error is not None
    assert "Timeout" in doc.error
    assert doc.content == ""


# =====================================================================
# 5. Deep Research Orchestrator  (2 tests)
# =====================================================================


def test_deep_research_event_to_sse():
    """DeepResearchEvent.to_sse() produces valid SSE format."""
    event = DeepResearchEvent("phase", {"phase": "decomposition", "iteration": 1})
    sse = event.to_sse()

    assert sse.startswith("data: ")
    assert sse.endswith("\n\n")

    payload = json.loads(sse[len("data: "):-2])
    assert payload["type"] == "phase"
    assert payload["phase"] == "decomposition"
    assert payload["iteration"] == 1


@patch("search.deep_research.graph_bridge")
@patch("search.deep_research.synthesize")
@patch("search.deep_research.decompose")
def test_orchestrator_stop_halts_iteration(
    mock_decompose, mock_synthesize, mock_graph_bridge
):
    """Calling stop() before run() prevents iteration events."""
    from search.deep_research import DeepResearchOrchestrator

    async def _run():
        orch = DeepResearchOrchestrator()
        orch.pipeline = MagicMock()
        orch.stop()

        events = []
        async for event in orch.run("test query", max_iterations=3):
            events.append(event)
        return events

    events = asyncio.run(_run())

    # Should get a done event (from the try block completing) but no phase events
    phase_events = [e for e in events if e.type_ == "phase"]
    assert len(phase_events) == 0

    done_events = [e for e in events if e.type_ == "done"]
    assert len(done_events) == 1


# =====================================================================
# 6. Cache  (2 tests)
# =====================================================================


def test_cache_get_or_none_miss_on_empty():
    """get_or_none returns None on an empty cache."""
    from search import cache

    cache.clear()
    assert cache.get_or_none("anything") is None


@patch("search.cache.get_embedding", create=True)
def test_cache_put_and_size(mock_import):
    """put() increments size; clear() resets to zero."""
    from search import cache

    cache.clear()
    assert cache.size() == 0

    # Mock get_embedding at the point it's imported inside put()
    fake_vec = np.random.randn(768).astype("float32")
    with patch("remme.utils.get_embedding", return_value=fake_vec):
        cache.put("test query", {"answer": "test result"})

    assert cache.size() == 1

    cache.clear()
    assert cache.size() == 0


# =====================================================================
# 7. Graph Bridge  (1 test)
# =====================================================================


def test_graph_bridge_session_lifecycle(tmp_path):
    """Full lifecycle: create -> add search -> add synthesis -> done."""
    from search import graph_bridge

    # Point graph_bridge to tmp_path for filesystem isolation
    original_base = graph_bridge._SESSIONS_BASE
    graph_bridge._SESSIONS_BASE = tmp_path

    try:
        run_id = "test_run_001"

        # Create session
        path = graph_bridge.create_deep_research_session(run_id, "test query")
        assert path.exists()

        data = json.loads(path.read_text())
        assert data["graph"]["research_mode"] == "deep_research"
        assert data["graph"]["status"] == "running"

        # Add search nodes
        graph_bridge.add_search_nodes(run_id, ["sq1", "sq2"], iteration=1)
        data = json.loads(path.read_text())
        node_ids = [n["id"] for n in data["nodes"]]
        assert "I1_Search_1" in node_ids
        assert "I1_Search_2" in node_ids

        # Add synthesis node
        synth_id = graph_bridge.add_synthesis_node(run_id, iteration=1)
        assert synth_id == "I1_Synthesize"

        # Mark iteration done
        graph_bridge.mark_iteration_done(run_id, 1, "synthesis output")
        data = json.loads(path.read_text())
        synth_node = next(n for n in data["nodes"] if n["id"] == "I1_Synthesize")
        assert synth_node["status"] == "completed"

        # Mark session done
        graph_bridge.mark_session_done(run_id)
        data = json.loads(path.read_text())
        assert data["graph"]["status"] == "completed"

    finally:
        graph_bridge._SESSIONS_BASE = original_base
