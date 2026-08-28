from pathlib import Path


def test_project_structure():
    root = Path(__file__).resolve().parents[1]
    assert (root / "main.py").exists()
    assert (root / "app" / "ui" / "overlay.py").exists()
    assert (root / "README.md").exists()
