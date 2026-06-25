"""Unit tests for src/extractor/differ.py."""
import pytest


class TestDiffContentNoChange:
    def test_unchanged_content_returns_changed_false(self):
        from src.extractor.differ import diff_content
        result = diff_content("line one\nline two", "line one\nline two")
        assert result["changed"] is False
        assert result["added"] == []
        assert result["removed"] == []


class TestDiffContentAddedLine:
    def test_detects_added_line(self):
        from src.extractor.differ import diff_content
        result = diff_content("line one", "line one\nline two")
        assert result["changed"] is True
        assert "line two" in result["added"]
        assert result["removed"] == []


class TestDiffContentRemovedLine:
    def test_detects_removed_line(self):
        from src.extractor.differ import diff_content
        result = diff_content("line one\nline two", "line one")
        assert result["changed"] is True
        assert "line two" in result["removed"]
        assert result["added"] == []


class TestDiffContentBothChanges:
    def test_detects_both_add_and_remove(self):
        from src.extractor.differ import diff_content
        result = diff_content("old line\ncommon", "new line\ncommon")
        assert result["changed"] is True
        assert any("old line" in r for r in result["removed"])
        assert any("new line" in a for a in result["added"])
