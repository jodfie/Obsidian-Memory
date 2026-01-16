"""Placeholder tests to verify test infrastructure works."""


def test_placeholder_passes() -> None:
    """Placeholder test that always passes."""
    assert True


def test_fixtures_available(temp_dir, sample_vault, sample_markdown) -> None:
    """Verify fixtures are available and working."""
    assert temp_dir.exists()
    assert sample_vault.exists()
    assert (sample_vault / "_claude-mem").exists()
    assert len(sample_markdown) > 0
