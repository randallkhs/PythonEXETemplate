import subprocess
import sys
from pathlib import Path


def main() -> None:
    script_path = Path(__file__).resolve().parent / "run.sh"
    if not script_path.exists():
        print("ERROR: run.sh was not found next to app.py")
        sys.exit(1)
    subprocess.run(["bash", str(script_path)], check=True)


if __name__ == "__main__":
    main()
