"""Tests for the ContentPicker dialog."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lgtvtools.mirror.content_picker import ContentPicker  # noqa: E402
from lgtvtools.mirror.models import CaptureSource  # noqa: E402


@pytest.fixture
def sample_sources() -> list[CaptureSource]:
    """Provide sample capture sources for testing."""
    return [
        CaptureSource(id="1", name="Display 1", kind="screen", resolution=(1920, 1080)),
        CaptureSource(id="2", name="Display 2", kind="screen", resolution=(2560, 1440)),
        CaptureSource(id="title=Firefox", name="Firefox", kind="window", resolution=None),
    ]


@pytest.fixture
def empty_sources() -> list[CaptureSource]:
    """Provide an empty list of sources for testing edge cases."""
    return []


class TestContentPicker:
    """Tests for ContentPicker dialog."""

    def test_picker_with_sources_stores_sources(
        self, qtbot, sample_sources: list[CaptureSource]
    ) -> None:
        """ContentPicker should store the provided sources."""
        picker = ContentPicker(sample_sources)
        qtbot.addWidget(picker)

        assert picker._sources == sample_sources

    def test_picker_displays_all_sources(
        self, qtbot, sample_sources: list[CaptureSource]
    ) -> None:
        """ContentPicker should display all sources in the list widget."""
        picker = ContentPicker(sample_sources)
        qtbot.addWidget(picker)

        assert picker._list_widget.count() == len(sample_sources)

    def test_picker_formats_source_with_resolution(
        self, qtbot, sample_sources: list[CaptureSource]
    ) -> None:
        """Source labels should include name, kind, and resolution when available."""
        picker = ContentPicker(sample_sources)
        qtbot.addWidget(picker)

        # First item has resolution
        first_item = picker._list_widget.item(0)
        assert first_item is not None
        text = first_item.text()
        assert "Display 1" in text
        assert "screen" in text
        assert "1920x1080" in text

    def test_picker_formats_source_without_resolution(
        self, qtbot, sample_sources: list[CaptureSource]
    ) -> None:
        """Source labels should work without resolution."""
        picker = ContentPicker(sample_sources)
        qtbot.addWidget(picker)

        # Third item has no resolution
        third_item = picker._list_widget.item(2)
        assert third_item is not None
        text = third_item.text()
        assert "Firefox" in text
        assert "window" in text
        # Should not have resolution
        assert "x" not in text.split(")")[-1]

    def test_picker_selects_first_item_by_default(
        self, qtbot, sample_sources: list[CaptureSource]
    ) -> None:
        """ContentPicker should select the first item by default."""
        picker = ContentPicker(sample_sources)
        qtbot.addWidget(picker)

        assert picker._list_widget.currentRow() == 0

    def test_picker_with_empty_sources(
        self, qtbot, empty_sources: list[CaptureSource]
    ) -> None:
        """ContentPicker should handle empty source list gracefully."""
        picker = ContentPicker(empty_sources)
        qtbot.addWidget(picker)

        assert picker._list_widget.count() == 0
        assert picker._list_widget.currentRow() == -1
        # OK button should be disabled
        assert not picker._ok_button.isEnabled()

    def test_selected_source_returns_none_before_accept(
        self, qtbot, sample_sources: list[CaptureSource]
    ) -> None:
        """selected_source should return None before dialog is accepted."""
        picker = ContentPicker(sample_sources)
        qtbot.addWidget(picker)

        assert picker.selected_source() is None

    def test_selected_source_returns_correct_source_after_accept(
        self, qtbot, sample_sources: list[CaptureSource]
    ) -> None:
        """selected_source should return the selected source after accept."""
        picker = ContentPicker(sample_sources)
        qtbot.addWidget(picker)

        # Select second item
        picker._list_widget.setCurrentRow(1)

        # Simulate accepting
        picker._on_accepted()

        selected = picker.selected_source()
        assert selected is not None
        assert selected.id == "2"
        assert selected.name == "Display 2"

    def test_format_source_label_screen_with_resolution(
        self, qtbot, sample_sources: list[CaptureSource]  # noqa: ARG002
    ) -> None:
        """_format_source_label should correctly format screen with resolution."""
        picker = ContentPicker([])
        qtbot.addWidget(picker)

        source = CaptureSource(
            id="1", name="Main Display", kind="screen", resolution=(3840, 2160)
        )
        label = picker._format_source_label(source)

        assert label == "Main Display (screen) - 3840x2160"

    def test_format_source_label_window_without_resolution(
        self, qtbot, sample_sources: list[CaptureSource]  # noqa: ARG002
    ) -> None:
        """_format_source_label should handle window without resolution."""
        picker = ContentPicker([])
        qtbot.addWidget(picker)

        source = CaptureSource(id="title=App", name="My App", kind="window")
        label = picker._format_source_label(source)

        assert label == "My App (window)"
