import subprocess
import sys


def test_cli_help_imports_without_circular_import():
    result = subprocess.run(
        [sys.executable, "-m", "backend.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "seed-one" in result.stdout
    assert "circular import" not in result.stderr.lower()
