"""Infrastructure & unit tests — fast pre-build gate for CI.

Verify project structure, packaging metadata, build configuration,
and Python package sanity without requiring compilation or GPU access.
Runs in under 10 seconds and gates all downstream CI stages.

Similar in purpose to the upstream MLC-LLM Jenkinsfile unittest stage
(ci/jenkinsfile.groovy) but scoped to what can run without hardware.

Usage:
    pytest tests/test_infra.py -v
"""

import re
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


# ── Project Structure ────────────────────────────────────────────────────────


class TestProjectStructure:
    """Essential files and directories exist."""

    def test_cmakelists_exists(self):
        assert (ROOT / "CMakeLists.txt").is_file()

    def test_tvm_submodule_configured(self):
        """TVM must be declared as a git submodule."""
        gitmodules = ROOT / ".gitmodules"
        assert gitmodules.is_file(), ".gitmodules not found"
        assert "3rdparty/tvm" in gitmodules.read_text()

    def test_python_package_exists(self):
        assert (ROOT / "python" / "mlc_llm" / "__init__.py").is_file()

    def test_docker_files_exist(self):
        for name in ["Dockerfile", "build-entrypoint.sh", "config.cmake"]:
            assert (ROOT / "docker" / name).is_file(), f"docker/{name} missing"

    def test_ci_workflow_exists(self):
        assert (ROOT / ".github" / "workflows" / "ci.yml").is_file()

    def test_composite_action_exists(self):
        assert (ROOT / ".github" / "actions" / "setup-build-env" / "action.yml").is_file()


# ── Packaging Metadata ───────────────────────────────────────────────────────


class TestPackagingMetadata:
    """pyproject.toml is valid and consistent."""

    @pytest.fixture(scope="class")
    def pyproject(self):
        with open(ROOT / "pyproject.toml", "rb") as f:
            return tomllib.load(f)

    def test_pyproject_has_project_section(self, pyproject):
        assert "project" in pyproject

    def test_package_name(self, pyproject):
        assert pyproject["project"]["name"] == "mlc_llm"

    def test_version_present(self, pyproject):
        version = pyproject["project"]["version"]
        assert any(c.isdigit() for c in version), f"Invalid version: {version}"

    def test_build_system_defined(self, pyproject):
        assert "build-system" in pyproject
        assert "requires" in pyproject["build-system"]

    def test_python_requires(self, pyproject):
        assert "requires-python" in pyproject["project"]

    def test_version_is_semver(self, pyproject):
        """Version string should follow semver (e.g. 0.1.0, 1.2.3)."""
        version = pyproject["project"]["version"]
        assert re.match(r"^\d+\.\d+", version), f"Not semver-like: {version}"


# ── Build Configuration ──────────────────────────────────────────────────────


class TestBuildConfiguration:
    """CI/Docker build configuration is valid."""

    @pytest.fixture(scope="class")
    def cmake_config(self):
        return (ROOT / "docker" / "config.cmake").read_text()

    def test_tvm_source_dir_set(self, cmake_config):
        assert "TVM_SOURCE_DIR" in cmake_config

    def test_cuda_disabled_for_ci(self, cmake_config):
        """CI builds must not require CUDA hardware."""
        assert "set(USE_CUDA OFF)" in cmake_config

    def test_entrypoint_activates_conda(self):
        content = (ROOT / "docker" / "build-entrypoint.sh").read_text()
        assert "conda activate" in content

    def test_entrypoint_supports_build_mode(self):
        content = (ROOT / "docker" / "build-entrypoint.sh").read_text()
        assert "build)" in content

    def test_entrypoint_supports_validate_mode(self):
        content = (ROOT / "docker" / "build-entrypoint.sh").read_text()
        assert "validate)" in content

    def test_entrypoint_is_executable_syntax(self):
        """Entrypoint must have a valid shebang line."""
        content = (ROOT / "docker" / "build-entrypoint.sh").read_text()
        assert content.startswith("#!/"), "Missing shebang in entrypoint"


# ── CI Workflow Validation ───────────────────────────────────────────────────


class TestCIWorkflow:
    """The GitHub Actions workflow is structurally sound."""

    @pytest.fixture(scope="class")
    def ci_content(self):
        return (ROOT / ".github" / "workflows" / "ci.yml").read_text()

    def test_workflow_has_test_job(self, ci_content):
        """A test job must exist to gate downstream stages."""
        assert "test:" in ci_content or "Test" in ci_content

    def test_docker_job_needs_test(self, ci_content):
        """Docker job should depend on tests passing."""
        assert "needs:" in ci_content

    def test_workflow_triggers_on_push(self, ci_content):
        assert "push:" in ci_content

    def test_workflow_triggers_on_pr(self, ci_content):
        assert "pull_request:" in ci_content


# ── Python Package Unit Tests ────────────────────────────────────────────────


class TestPythonPackage:
    """Verify the Python package source is importable and well-formed.

    These tests add the local source to sys.path and check that key
    modules parse correctly — similar to the upstream Jenkinsfile's
    unittest stage but without requiring native compilation.
    """

    @pytest.fixture(autouse=True, scope="class")
    def add_python_source_to_path(self):
        """Temporarily add python/ to the path for import checks."""
        src = str(ROOT / "python")
        if src not in sys.path:
            sys.path.insert(0, src)
        yield
        if src in sys.path:
            sys.path.remove(src)

    def test_mlc_llm_package_has_init(self):
        init = ROOT / "python" / "mlc_llm" / "__init__.py"
        assert init.is_file()
        content = init.read_text()
        assert len(content) > 0, "__init__.py should not be empty"

    def test_mlc_llm_has_version_info(self):
        """Package should expose version metadata."""
        pyproject = ROOT / "pyproject.toml"
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        assert "version" in data["project"]

    def test_python_syntax_valid(self):
        """All .py files under python/mlc_llm/ must be valid syntax."""
        pkg_dir = ROOT / "python" / "mlc_llm"
        errors = []
        for py_file in pkg_dir.rglob("*.py"):
            try:
                compile(py_file.read_text(), str(py_file), "exec")
            except SyntaxError as e:
                errors.append(f"{py_file}: {e}")
        assert not errors, f"Syntax errors found:\n" + "\n".join(errors)
