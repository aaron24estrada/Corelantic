"""Export the OpenAPI schema to openapi.json, the input for typed client generation.

The web app's ``gen:api`` script turns this file into TypeScript types. Regenerate with
``make client`` from the repo root whenever the API contract changes.
"""

import json
from pathlib import Path

from app.main import app


def main() -> None:
    schema = app.openapi()
    output = Path(__file__).resolve().parents[1] / "openapi.json"
    output.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
