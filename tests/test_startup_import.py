import subprocess
import sys


def test_importing_app_does_not_require_escpos() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import taskmanagement_app.main; assert 'escpos' not in sys.modules",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
