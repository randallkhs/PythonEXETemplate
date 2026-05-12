"""Application entry for PyInstaller and ``python app.py`` (Windows + macOS).

Use ``run.sh`` for local development with a managed ``.venv`` on Unix.
"""

from __future__ import annotations


def main() -> None:
    from app.gui import run

    run()


if __name__ == "__main__":
    main()
