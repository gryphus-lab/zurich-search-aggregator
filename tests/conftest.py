import sys
from pathlib import Path


def pytest_configure():
    # Ensure `import src...` works when tests are run from repo root.
    """
    Ensure the repository root is on sys.path so top-level imports from the repo (e.g. `import src...`) work when running tests.
    
    If the repository root is not already present in sys.path, it is prepended to enable imports relative to the project root.
    """
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
