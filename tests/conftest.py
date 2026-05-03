import sys
from pathlib import Path


def pytest_configure():
    # Ensure `import src...` works when tests are run from repo root.
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
