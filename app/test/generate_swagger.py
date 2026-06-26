from __future__ import annotations

import json
from pathlib import Path

from app.main import app


def main() -> None:
    output_path = Path(__file__).with_name("swagger.json")
    output_path.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Swagger schema written to: {output_path}")


if __name__ == "__main__":
    main()
