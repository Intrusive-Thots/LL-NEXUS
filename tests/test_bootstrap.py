def test_bootstrap_imports_and_constructs():
    """Verify that bootstrap module imports cleanly and can be inspected."""
    from nexus.app.bootstrap import main
    assert callable(main)
