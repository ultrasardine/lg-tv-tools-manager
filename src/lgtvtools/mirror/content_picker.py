"""Content picker dialog for screen/window selection.

This module provides a Qt dialog for selecting a capture source (screen or window)
to mirror. It displays available capture sources in a list and allows the user
to select one or cancel the operation.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .models import CaptureSource

LOGGER = logging.getLogger(__name__)


class ContentPicker(QDialog):
    """Qt dialog for selecting a screen or window to capture.

    Displays a list of available capture sources and allows the user to select
    one for screen mirroring. If the user cancels, selected_source() returns None.

    Example:
        sources = enumerate_sources(platform)
        picker = ContentPicker(sources, parent=main_window)
        if picker.exec() == QDialog.DialogCode.Accepted:
            source = picker.selected_source()
            # Start mirroring with source
    """

    def __init__(
        self, sources: list[CaptureSource], parent: QWidget | None = None
    ) -> None:
        """Initialize the content picker dialog.

        Args:
            sources: List of available capture sources to display.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._sources = sources
        self._selected: CaptureSource | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the dialog UI layout."""
        self.setWindowTitle("Select Content to Mirror")
        self.setMinimumWidth(350)
        self.setMinimumHeight(250)

        layout = QVBoxLayout(self)

        # Header label
        header = QLabel("Choose a screen or window to mirror:")
        layout.addWidget(header)

        # List widget for sources
        self._list_widget = QListWidget()
        self._list_widget.setAlternatingRowColors(True)
        self._list_widget.itemDoubleClicked.connect(self._on_double_click)

        for source in self._sources:
            item = QListWidgetItem()
            item.setText(self._format_source_label(source))
            item.setData(Qt.ItemDataRole.UserRole, source)
            self._list_widget.addItem(item)

        # Select the first item by default if available
        if self._sources:
            self._list_widget.setCurrentRow(0)

        layout.addWidget(self._list_widget)

        # OK/Cancel buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accepted)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Update OK button state based on selection
        self._list_widget.currentRowChanged.connect(self._update_ok_button)
        self._ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self._update_ok_button()

    def _format_source_label(self, source: CaptureSource) -> str:
        """Format a source for display in the list.

        Args:
            source: The capture source to format.

        Returns:
            A human-readable string showing name, kind, and optionally resolution.
        """
        label = f"{source.name} ({source.kind})"
        if source.resolution:
            width, height = source.resolution
            label += f" - {width}x{height}"
        return label

    def _update_ok_button(self) -> None:
        """Enable/disable OK button based on selection state."""
        has_selection = self._list_widget.currentRow() >= 0
        if self._ok_button:
            self._ok_button.setEnabled(has_selection)

    def _on_double_click(self, item: QListWidgetItem) -> None:  # noqa: ARG002
        """Handle double-click on a list item to accept immediately."""
        self._on_accepted()

    def _on_accepted(self) -> None:
        """Handle dialog acceptance."""
        current_item = self._list_widget.currentItem()
        if current_item:
            self._selected = current_item.data(Qt.ItemDataRole.UserRole)
            LOGGER.debug("Selected source: %s", self._selected)
        self.accept()

    def selected_source(self) -> CaptureSource | None:
        """Returns the user-selected source, or None if cancelled.

        This method should be called after the dialog has been closed
        (i.e., after exec() returns).

        Returns:
            The selected CaptureSource, or None if the dialog was cancelled
            or no selection was made.
        """
        return self._selected
