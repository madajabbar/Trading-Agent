import argparse
from pathlib import Path

def convert_py_to_txt(folder: Path, recursive: bool) -> None:
    pattern = "**/*.py" if recursive else "*.py"
    for py_file in folder.glob(pattern):
        if py_file.is_file():
            txt_file = py_file.with_suffix(".txt")
            txt_file.write_text(py_file.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"{py_file} -> {txt_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Konversi .py ke .txt dalam folder.")
    parser.add_argument("folder", nargs="?", default=".", help="Path folder (default: current folder)")
    parser.add_argument("-r", "--recursive", action="store_true", help="Proses juga subfolder")
    args = parser.parse_args()

    convert_py_to_txt(Path(args.folder), args.recursive)