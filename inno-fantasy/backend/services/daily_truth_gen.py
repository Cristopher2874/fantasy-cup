"""Daily source-of-truth generation entrypoint."""
from __future__ import annotations

from services.data_generator.source_of_truth import main as source_truth_main


if __name__ == "__main__":
    raise SystemExit(source_truth_main())
