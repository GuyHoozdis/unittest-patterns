"""Nox sessions."""

# https://nox.thea.codes/en/stable/config.html#modifying-nox-s-behavior-in-the-noxfile
import nox
from nox.sessions import Session

nox.options.sessions = "lint", "style", "mypy", "tests"
nox.options.stop_on_first_error = False
nox.options.error_on_external_run = True

DEFAULT_PYTHON_VERSION = "3.11"
SUPPORTED_PYTHON_VERSIONS = ["3.13", "3.12", "3.11"]
SOURCE_CODE_TARGETS = ["tests/", "./noxfile.py", "src/"]


@nox.session(python=SUPPORTED_PYTHON_VERSIONS, venv_backend="uv")
def mypy(session: Session) -> None:
    """Run static type checking using mypy."""
    args = session.posargs or SOURCE_CODE_TARGETS
    session.run_install("uv", "sync", "--extra=test", env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location})
    session.run("mypy", *args)


@nox.session(python=DEFAULT_PYTHON_VERSION)
def lint(session: Session) -> None:
    """Analyze code for errors using ruff."""
    args = session.posargs or SOURCE_CODE_TARGETS
    session.install("ruff")
    session.run("ruff", "check", *args)


@nox.session(python=DEFAULT_PYTHON_VERSION)
def style(session: Session) -> None:
    """Validate style using ruff."""
    args = session.posargs or SOURCE_CODE_TARGETS
    session.install("ruff")
    session.run("ruff", "format", "--check", *args)


@nox.session(python=DEFAULT_PYTHON_VERSION, default=False)
def autofix(session: Session) -> None:
    """Apply fixable lint and style fixes."""
    args = session.posargs or SOURCE_CODE_TARGETS
    session.install("ruff")
    session.log("Fixing fixable lint errors... if any")
    session.run("ruff", "check", "--fix", *args)
    session.log("Fixing fixable style errors... if any")
    session.run("ruff", "format", *args)


@nox.session(python=SUPPORTED_PYTHON_VERSIONS, venv_backend="uv")
def tests(session: Session) -> None:
    """Run the test suite."""
    args = session.posargs or ["discover", "--start-directory", "tests/", "--top-level-directory", "."]
    session.run_install("uv", "sync", "--extra=test", env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location})
    session.run("coverage", "run", "-m", "unittest", *args)
    session.log("Run the coverage task to generate a report after running the tests.")


@nox.session(python=DEFAULT_PYTHON_VERSION)
def coverage(session: Session) -> None:
    """Generate coverage report."""
    session.install("coverage[toml]")
    session.run("coverage", "combine")
    session.run("coverage", "xml")
    session.run("coverage", "json")
    session.run("coverage", "html", *session.posargs)
    session.run("coverage", "report")
    session.log("Open the coverage report in your browser with the command:")
    session.log("$ open coverage/html/index.html")
