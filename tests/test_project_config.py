"""
Tests for the project configuration files changed in the uv migration PR.

Validates the structure and content of:
- pyproject.toml: project metadata, dependencies, build system, uv settings
- mise.toml: tools, tasks, and uv run command prefixes
- requirements.txt: should have been deleted
- uv.lock: should exist with correct format
"""

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
MISE_PATH = REPO_ROOT / "mise.toml"
REQUIREMENTS_PATH = REPO_ROOT / "requirements.txt"
UV_LOCK_PATH = REPO_ROOT / "uv.lock"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def load_pyproject() -> dict:
    with PYPROJECT_PATH.open("rb") as f:
        return tomllib.load(f)


def load_mise() -> dict:
    with MISE_PATH.open("rb") as f:
        return tomllib.load(f)


# ---------------------------------------------------------------------------
# pyproject.toml – project metadata
# ---------------------------------------------------------------------------


def test_pyproject_project_name():
    data = load_pyproject()
    assert data["project"]["name"] == "zurich-search-aggregator"


def test_pyproject_description_is_set():
    """Description was changed from placeholder to a real description in this PR."""
    data = load_pyproject()
    description = data["project"]["description"]
    assert description, "description must not be empty"
    assert description != "Add your description here", (
        "description must be updated from placeholder"
    )


def test_pyproject_python_version_requirement():
    data = load_pyproject()
    requires = data["project"]["requires-python"]
    assert requires == ">=3.14"


def test_pyproject_version():
    data = load_pyproject()
    assert data["project"]["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# pyproject.toml – runtime dependencies (was empty list before this PR)
# ---------------------------------------------------------------------------

EXPECTED_RUNTIME_DEPS = [
    "beautifulsoup4",
    "filters",
    "httpx",
    "lxml",
    "pandas",
    "playwright",
    "pydantic",
    "python-dateutil",
    "python-dotenv",
    "rich",
    "typer",
]


def _dep_names(deps: list[str]) -> list[str]:
    """Extract package names from PEP 508 dependency strings."""
    return [re.split(r"[><=!;\[]", d)[0].strip() for d in deps]


def test_pyproject_runtime_dependencies_not_empty():
    """Before this PR dependencies was an empty list; it must now have entries."""
    data = load_pyproject()
    deps = data["project"]["dependencies"]
    assert len(deps) > 0, "runtime dependencies must not be empty"


def test_pyproject_all_runtime_deps_present():
    data = load_pyproject()
    dep_names = _dep_names(data["project"]["dependencies"])
    for pkg in EXPECTED_RUNTIME_DEPS:
        assert pkg in dep_names, f"expected runtime dependency '{pkg}' not found"


def test_pyproject_dep_beautifulsoup4_version():
    data = load_pyproject()
    deps = data["project"]["dependencies"]
    bs4 = next((d for d in deps if d.startswith("beautifulsoup4")), None)
    assert bs4 is not None
    assert "4.14.3" in bs4


def test_pyproject_dep_pydantic_version():
    data = load_pyproject()
    deps = data["project"]["dependencies"]
    pydantic = next((d for d in deps if d.startswith("pydantic") and "core" not in d), None)
    assert pydantic is not None
    assert "2.13.3" in pydantic


def test_pyproject_dep_playwright_version():
    data = load_pyproject()
    deps = data["project"]["dependencies"]
    playwright = next((d for d in deps if d.startswith("playwright")), None)
    assert playwright is not None
    assert "1.59.0" in playwright


def test_pyproject_dep_httpx_version():
    data = load_pyproject()
    deps = data["project"]["dependencies"]
    httpx = next((d for d in deps if d.startswith("httpx")), None)
    assert httpx is not None
    assert "0.28.1" in httpx


# ---------------------------------------------------------------------------
# pyproject.toml – build system (new in this PR)
# ---------------------------------------------------------------------------


def test_pyproject_build_system_present():
    data = load_pyproject()
    assert "build-system" in data, "[build-system] section must be present"


def test_pyproject_build_system_requires_hatchling():
    data = load_pyproject()
    requires = data["build-system"]["requires"]
    assert "hatchling" in requires


def test_pyproject_build_backend_is_hatchling():
    data = load_pyproject()
    assert data["build-system"]["build-backend"] == "hatchling.build"


def test_pyproject_hatch_wheel_packages():
    data = load_pyproject()
    packages = data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert "src/aggregator" in packages


# ---------------------------------------------------------------------------
# pyproject.toml – uv configuration (new in this PR)
# ---------------------------------------------------------------------------


def test_pyproject_uv_managed_true():
    """[tool.uv] managed = true was added in this PR."""
    data = load_pyproject()
    assert data["tool"]["uv"]["managed"] is True


def test_pyproject_uv_sources_section_exists():
    """[tool.uv.sources] section was added (even if empty) to allow future overrides."""
    data = load_pyproject()
    assert "sources" in data["tool"]["uv"]


# ---------------------------------------------------------------------------
# pyproject.toml – dev dependency-groups (new in this PR)
# ---------------------------------------------------------------------------

EXPECTED_DEV_DEPS = ["pytest", "pytest-cov", "ruff"]


def test_pyproject_dev_dependency_group_present():
    data = load_pyproject()
    assert "dev" in data["dependency-groups"], "[dependency-groups].dev must be present"


def test_pyproject_dev_group_has_pytest():
    data = load_pyproject()
    dev_deps = _dep_names(data["dependency-groups"]["dev"])
    assert "pytest" in dev_deps


def test_pyproject_dev_group_has_pytest_cov():
    data = load_pyproject()
    dev_deps = _dep_names(data["dependency-groups"]["dev"])
    assert "pytest-cov" in dev_deps


def test_pyproject_dev_group_has_ruff():
    data = load_pyproject()
    dev_deps = _dep_names(data["dependency-groups"]["dev"])
    assert "ruff" in dev_deps


def test_pyproject_dev_group_pytest_version():
    data = load_pyproject()
    dev = data["dependency-groups"]["dev"]
    pytest_dep = next((d for d in dev if d.startswith("pytest>=")), None)
    assert pytest_dep is not None
    assert "9.0.3" in pytest_dep


def test_pyproject_dev_group_ruff_version():
    data = load_pyproject()
    dev = data["dependency-groups"]["dev"]
    ruff_dep = next((d for d in dev if d.startswith("ruff")), None)
    assert ruff_dep is not None
    assert ">=" in ruff_dep


def test_pyproject_dev_tools_not_in_runtime_deps():
    """Dev-only tools (pytest, ruff) must NOT appear in runtime dependencies."""
    data = load_pyproject()
    runtime_names = _dep_names(data["project"]["dependencies"])
    assert "pytest" not in runtime_names, "pytest must be a dev-only dependency"
    assert "ruff" not in runtime_names, "ruff must be a dev-only dependency"
    assert "pytest-cov" not in runtime_names, "pytest-cov must be a dev-only dependency"


# ---------------------------------------------------------------------------
# mise.toml – tools section
# ---------------------------------------------------------------------------


def test_mise_has_python_tool():
    data = load_mise()
    assert "python" in data["tools"]
    assert data["tools"]["python"] == "3.14"


def test_mise_has_uv_tool():
    data = load_mise()
    assert "uv" in data["tools"]
    assert data["tools"]["uv"] == "latest"


def test_mise_no_standalone_ruff_tool():
    """ruff was removed as a mise tool in this PR; it is now managed via uv."""
    data = load_mise()
    assert "ruff" not in data["tools"], (
        "ruff should not be a standalone mise tool; use 'uv run ruff' instead"
    )


# ---------------------------------------------------------------------------
# mise.toml – settings
# ---------------------------------------------------------------------------


def test_mise_uv_venv_auto_disabled():
    """python.uv_venv_auto was changed from 'create|source' to false.

    In TOML, 'python.uv_venv_auto = false' under [settings] creates a nested
    dict: settings -> python -> uv_venv_auto.
    """
    data = load_mise()
    # Dotted keys in TOML become nested dicts
    assert data["settings"]["python"]["uv_venv_auto"] is False


def test_mise_no_venv_env_vars():
    """UV_PROJECT_ENVIRONMENT was removed; venv is now managed by uv itself."""
    data = load_mise()
    env = data.get("env", {})
    assert "UV_PROJECT_ENVIRONMENT" not in env


# ---------------------------------------------------------------------------
# mise.toml – bootstrap task
# ---------------------------------------------------------------------------


def test_mise_bootstrap_uses_uv_sync_all_groups():
    """bootstrap must use 'uv sync --all-groups' instead of 'uv pip install -r requirements.txt'."""
    data = load_mise()
    run_cmds = data["tasks"]["bootstrap"]["run"]
    assert isinstance(run_cmds, list), "bootstrap.run should be a list of commands"
    sync_cmd = next((c for c in run_cmds if "uv sync" in c), None)
    assert sync_cmd is not None, "bootstrap must contain a 'uv sync' command"
    assert "--all-groups" in sync_cmd, "uv sync must include --all-groups flag"


def test_mise_bootstrap_does_not_use_pip_install():
    """Old 'uv pip install -r requirements.txt' must be gone."""
    data = load_mise()
    run_cmds = data["tasks"]["bootstrap"]["run"]
    for cmd in run_cmds:
        assert "pip install" not in cmd, (
            "bootstrap must not use 'uv pip install'; use 'uv sync' instead"
        )


def test_mise_bootstrap_playwright_install_uses_uv_run():
    data = load_mise()
    run_cmds = data["tasks"]["bootstrap"]["run"]
    playwright_cmd = next((c for c in run_cmds if "playwright install" in c), None)
    assert playwright_cmd is not None
    assert playwright_cmd.startswith("uv run "), (
        "playwright install must be prefixed with 'uv run'"
    )


def test_mise_bootstrap_does_not_reference_requirements_txt():
    data = load_mise()
    run_cmds = data["tasks"]["bootstrap"]["run"]
    for cmd in run_cmds:
        assert "requirements.txt" not in cmd, (
            "bootstrap must not reference requirements.txt; dependencies are in pyproject.toml"
        )


# ---------------------------------------------------------------------------
# mise.toml – tasks use 'uv run' prefix
# ---------------------------------------------------------------------------


def test_mise_run_task_uses_uv_run():
    data = load_mise()
    cmd = data["tasks"]["run"]["run"]
    assert isinstance(cmd, str)
    assert cmd.startswith("uv run "), f"'run' task must use 'uv run' prefix, got: {cmd}"


def test_mise_scrape_task_uses_uv_run():
    data = load_mise()
    cmd = data["tasks"]["scrape"]["run"]
    assert isinstance(cmd, str)
    assert cmd.startswith("uv run "), f"'scrape' task must use 'uv run' prefix, got: {cmd}"


def test_mise_lint_task_uses_uv_run_for_ruff():
    data = load_mise()
    cmd = data["tasks"]["lint"]["run"]
    assert isinstance(cmd, str)
    assert "uv run ruff" in cmd, (
        f"'lint' task must use 'uv run ruff' instead of bare 'ruff', got: {cmd}"
    )


def test_mise_lint_task_no_bare_ruff():
    """Lint must not call bare 'ruff' without 'uv run' prefix."""
    data = load_mise()
    cmd = data["tasks"]["lint"]["run"]
    # Should not start with 'ruff' and should not have '&& ruff' without uv run
    assert not re.search(r"(?<![a-z])ruff(?!\s*=)", cmd.replace("uv run ruff", "")), (
        f"lint task contains bare 'ruff' call without 'uv run': {cmd}"
    )


def test_mise_format_task_uses_uv_run_for_ruff():
    data = load_mise()
    cmd = data["tasks"]["format"]["run"]
    assert isinstance(cmd, str)
    assert "uv run ruff" in cmd, (
        f"'format' task must use 'uv run ruff' instead of bare 'ruff', got: {cmd}"
    )


def test_mise_test_task_uses_uv_run():
    data = load_mise()
    cmd = data["tasks"]["test"]["run"]
    assert isinstance(cmd, str)
    assert cmd.startswith("uv run "), f"'test' task must use 'uv run' prefix, got: {cmd}"


def test_mise_test_task_targets_tests_directory():
    """Test task was updated to explicitly target the tests/ directory."""
    data = load_mise()
    cmd = data["tasks"]["test"]["run"]
    assert "tests" in cmd, f"'test' task should target the tests/ directory, got: {cmd}"


def test_mise_test_task_verbose_flag():
    """Test task now includes -v for verbose output."""
    data = load_mise()
    cmd = data["tasks"]["test"]["run"]
    assert "-v" in cmd, f"'test' task should include -v flag, got: {cmd}"


def test_mise_coverage_task_uses_uv_run():
    data = load_mise()
    cmd = data["tasks"]["coverage"]["run"]
    assert isinstance(cmd, str)
    assert cmd.startswith("uv run "), f"'coverage' task must use 'uv run' prefix, got: {cmd}"


def test_mise_test_task_does_not_use_bare_pytest():
    """Old tasks used bare 'pytest' without 'uv run'."""
    data = load_mise()
    cmd = data["tasks"]["test"]["run"]
    # Must start with uv run, not just 'pytest'
    assert not cmd.startswith("pytest"), (
        f"'test' task must not use bare 'pytest'; use 'uv run pytest', got: {cmd}"
    )


# ---------------------------------------------------------------------------
# mise.toml – task dependencies on bootstrap
# ---------------------------------------------------------------------------


def test_mise_run_task_depends_on_bootstrap():
    data = load_mise()
    depends = data["tasks"]["run"].get("depends", [])
    assert "bootstrap" in depends


def test_mise_test_task_depends_on_bootstrap():
    data = load_mise()
    depends = data["tasks"]["test"].get("depends", [])
    assert "bootstrap" in depends


def test_mise_coverage_task_depends_on_bootstrap():
    data = load_mise()
    depends = data["tasks"]["coverage"].get("depends", [])
    assert "bootstrap" in depends


# ---------------------------------------------------------------------------
# mise.toml – info task updated to show python version not venv
# ---------------------------------------------------------------------------


def test_mise_info_task_shows_python_version():
    """Info task was updated to show python --version instead of $VIRTUAL_ENV."""
    data = load_mise()
    cmd = data["tasks"]["info"]["run"]
    assert "python --version" in cmd, (
        "info task should show python version"
    )


def test_mise_info_task_does_not_show_virtual_env():
    """Info task must not reference $VIRTUAL_ENV (removed in this PR)."""
    data = load_mise()
    cmd = data["tasks"]["info"]["run"]
    assert "VIRTUAL_ENV" not in cmd, (
        "info task must not reference $VIRTUAL_ENV; show python --version instead"
    )


# ---------------------------------------------------------------------------
# requirements.txt – must have been deleted
# ---------------------------------------------------------------------------


def test_requirements_txt_does_not_exist():
    """requirements.txt was deleted in this PR; dependencies are in pyproject.toml."""
    assert not REQUIREMENTS_PATH.exists(), (
        "requirements.txt should have been deleted; use pyproject.toml with uv instead"
    )


# ---------------------------------------------------------------------------
# uv.lock – must exist with correct structure
# ---------------------------------------------------------------------------


def test_uv_lock_exists():
    """uv.lock must exist as the canonical lockfile for uv."""
    assert UV_LOCK_PATH.exists(), "uv.lock must exist for reproducible installs"


def test_uv_lock_is_not_empty():
    assert UV_LOCK_PATH.stat().st_size > 0, "uv.lock must not be empty"


def test_uv_lock_version_header():
    """uv.lock must start with 'version = 1'."""
    content = UV_LOCK_PATH.read_text()
    first_line = content.splitlines()[0].strip()
    assert first_line == "version = 1", f"uv.lock version header is unexpected: {first_line}"


def test_uv_lock_python_requirement():
    """uv.lock must enforce Python >= 3.14, matching pyproject.toml."""
    content = UV_LOCK_PATH.read_text()
    assert 'requires-python = ">=3.14"' in content, (
        "uv.lock must contain requires-python = '>=3.14'"
    )


def test_uv_lock_contains_key_packages():
    """Key runtime packages from pyproject.toml must appear in uv.lock."""
    content = UV_LOCK_PATH.read_text()
    key_packages = [
        "beautifulsoup4",
        "httpx",
        "lxml",
        "pandas",
        "playwright",
        "pydantic",
        "rich",
        "typer",
    ]
    for pkg in key_packages:
        assert f'name = "{pkg}"' in content, (
            f"uv.lock must contain package '{pkg}'"
        )


def test_uv_lock_contains_dev_packages():
    """Dev dependencies (pytest, ruff) must appear in uv.lock."""
    content = UV_LOCK_PATH.read_text()
    dev_packages = ["pytest", "ruff", "coverage"]
    for pkg in dev_packages:
        assert f'name = "{pkg}"' in content, (
            f"uv.lock must contain dev package '{pkg}'"
        )


def test_uv_lock_has_revision():
    """uv.lock must have a revision field indicating it was generated by uv."""
    content = UV_LOCK_PATH.read_text()
    assert "revision = " in content, "uv.lock must contain a revision field"


def test_uv_lock_packages_reference_pypi():
    """All packages in uv.lock should come from pypi.org."""
    content = UV_LOCK_PATH.read_text()
    assert "pypi.org" in content, "uv.lock packages should reference pypi.org"


# ---------------------------------------------------------------------------
# Cross-file consistency checks
# ---------------------------------------------------------------------------


def test_python_version_consistent_across_configs():
    """Python version in pyproject.toml and mise.toml must be consistent."""
    pyproject = load_pyproject()
    mise = load_mise()

    # pyproject requires >= 3.14, mise pins 3.14
    requires_python = pyproject["project"]["requires-python"]
    mise_python = mise["tools"]["python"]

    assert "3.14" in requires_python, "pyproject.toml must require Python 3.14"
    assert mise_python == "3.14", "mise.toml must pin Python 3.14"


def test_ruff_only_in_dev_not_as_mise_tool():
    """ruff should be a dev dependency in pyproject.toml, not a standalone mise tool."""
    pyproject = load_pyproject()
    mise = load_mise()

    dev_dep_names = _dep_names(pyproject["dependency-groups"]["dev"])
    assert "ruff" in dev_dep_names, "ruff must be in pyproject.toml dev dependencies"
    assert "ruff" not in mise["tools"], "ruff must NOT be a standalone mise tool"


def test_no_requirements_txt_and_uv_lock_present():
    """After migration: requirements.txt gone, uv.lock present."""
    assert not REQUIREMENTS_PATH.exists(), "requirements.txt must not exist after uv migration"
    assert UV_LOCK_PATH.exists(), "uv.lock must exist after uv migration"
