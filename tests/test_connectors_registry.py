"""Tests for the connector registry and manager resolution."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from connector_helpers import write_transcripts
from meeting_memory.connectors import (
    ConnectorCapability,
    ConnectorManager,
    ConnectorRegistry,
    ImportRequest,
    default_manager,
    default_registry,
)
from meeting_memory.connectors.base import (
    IMPORT_ARCHIVE,
    IMPORT_BATCH,
    IMPORT_DIRECTORY,
    IMPORT_RECURSIVE,
)
from meeting_memory.exceptions import UnknownConnectorError


def test_default_registry_lists_connectors() -> None:
    registry = default_registry()
    import_names = {connector.name for connector in registry.list_imports()}
    assert {"text", "json", "markdown", "csv", IMPORT_DIRECTORY, IMPORT_BATCH} <= import_names
    export_names = {connector.name for connector in registry.list_exports()}
    assert {"markdown", "json", "graph", "csv", "summary"} <= export_names
    assert "txt" in registry.import_formats()
    assert "markdown" in registry.export_formats()


def test_import_for_path_resolution(tmp_path: Path) -> None:
    registry = default_registry()
    source = write_transcripts(tmp_path / "data")
    assert registry.import_for_path(source).name == IMPORT_DIRECTORY
    assert registry.import_for_path(source, recursive=True).name == IMPORT_RECURSIVE
    assert registry.import_for_path(source / "a.txt").name == "text"
    assert registry.import_for_path(source / "b.json").name == "json"
    assert registry.import_for_path(source / "c.md").name == "markdown"

    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("a.txt", "Alice: hi")
    assert registry.import_for_path(archive).name == IMPORT_ARCHIVE


def test_import_for_unknown_extension(tmp_path: Path) -> None:
    registry = default_registry()
    bogus = tmp_path / "notes.rst"
    bogus.write_text("x", encoding="utf-8")
    with pytest.raises(UnknownConnectorError):
        registry.import_for_path(bogus)


def test_export_for_unknown_format() -> None:
    registry = default_registry()
    with pytest.raises(UnknownConnectorError):
        registry.export_for_format("pdf")


def test_get_unknown_connectors_raise() -> None:
    registry = ConnectorRegistry()
    with pytest.raises(UnknownConnectorError):
        registry.get_import("nope")
    with pytest.raises(UnknownConnectorError):
        registry.get_export("nope")
    with pytest.raises(UnknownConnectorError):
        registry.get_automation("nope")


def test_manager_resolves_batch_request() -> None:
    manager = default_manager()
    request = ImportRequest(source="", sources=("a.txt", "b.txt"))
    connector = manager._resolve_import(request)
    assert connector.name == IMPORT_BATCH


def test_manager_is_a_manager() -> None:
    registry = default_registry()
    manager = ConnectorManager(registry)
    assert manager.registry is registry


def test_directory_connector_capabilities() -> None:
    registry = default_registry()
    directory = registry.get_import(IMPORT_DIRECTORY)
    assert directory.supports(ConnectorCapability.DIRECTORY)
    assert not directory.supports(ConnectorCapability.RECURSIVE)
    recursive = registry.get_import(IMPORT_RECURSIVE)
    assert recursive.supports(ConnectorCapability.RECURSIVE)
