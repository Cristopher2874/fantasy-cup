"""Daily data generation entrypoint."""
from __future__ import annotations

from services.data_generator.public_data import main as public_data_main


if __name__ == "__main__":
    raise SystemExit(public_data_main())
