"""Allow `python -m backend.cli` to launch the CLI."""
from .main import main

if __name__ == "__main__":
    raise SystemExit(main())
