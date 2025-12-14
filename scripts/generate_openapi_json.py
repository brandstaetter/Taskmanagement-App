import json
from pathlib import Path

from taskmanagement_app.main import app


def main() -> None:
    output_path = Path("openapi.json")
    output_path.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
