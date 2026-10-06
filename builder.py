# ABE-Decryptor
# Author: encryptedroot
# Discord: encryptedroot
import os
import sys
import subprocess
import base64
from pathlib import Path
import re
from enum import Enum


class Color(Enum):
	RESET = "\033[0m"
	RED = "\033[31m"
	GREEN = "\033[32m"
	YELLOW = "\033[33m"
	CYAN = "\033[36m"
	WHITE = "\033[37m"


def log(message: str, color: Color = Color.RESET, symbol: str = ""):
	lines = message.split("\n")
	first_prefix = f"[{symbol}] " if symbol else ""

	for i, line in enumerate(lines):
		prefix = first_prefix if i == 0 else " " * len(first_prefix)
		print(f"{color.value}{prefix}{line}{Color.RESET.value}")


if __name__ == "__main__":
	input_file_name = "dllmain.cpp"
	dll_name = "crmodule.dll"
	python_file_name = "injector_template.py"
	output_file_name = "injector.py"

	root = Path(__file__).resolve().parent

	src = root / "src"
	build = root / "build"
	os.makedirs("build", exist_ok=True)

	cpp_path = src / input_file_name
	dll_path = build / dll_name
	py_path = src / python_file_name

	os.system("cls")

	print("ABE-Decryptor")
	print("by encryptedroot")
	print("discord: encryptedroot")

	if "DevEnvDir" not in os.environ:
		msg = (
			"ERROR: MSVC build environment not detected.\n"
			"This script must be run from a\n"
			'"x64 Native Tools Command Prompt for VS <version>".\n'
		)

		log(msg, Color.RED, "!")
		sys.exit(1)

	arch = os.environ.get("VSCMD_ARG_TGT_ARCH")
	if arch and arch.lower() != "x64":
		log(
			f"ERROR: {arch} build environment detected instead of x64.",
			Color.RED,
			"!"
		)
		sys.exit(1)

	if not cpp_path.is_file():
		log(f"Missing input file: {cpp_path}", Color.RED, "!")
		sys.exit(1)

	if not py_path.is_file():
		log(f"Missing Python file: {py_path}", Color.RED, "!")
		sys.exit(1)

	log(
		f"Compiling src/{cpp_path.name} -> build/{dll_path.name} ...",
		Color.CYAN,
		"*"
	)

	compile_cmd = [
		"cl",
		"/nologo",
		"/std:c++17",
		"/O2",
		"/EHsc",
		"/MT",
		"/LD",
		"/D", "NDEBUG",
		"/D", "CPPDYNAMICLIBRARYTEMPLATE_EXPORTS",
		"/D", "_WINDOWS",
		"/D", "_USRDLL",
		"/D", "_WINDLL",
		"/D", "_UNICODE",
		"/D", "UNICODE",
		str(cpp_path),
		f"/Fe:{dll_path}",
		"/link",
		"kernel32.lib",
		"user32.lib",
		"gdi32.lib",
		"winspool.lib",
		"comdlg32.lib",
		"advapi32.lib",
		"shell32.lib",
		"ole32.lib",
		"oleaut32.lib",
		"uuid.lib",
		"odbc32.lib",
		"odbccp32.lib",
	]

	result = subprocess.run(
		compile_cmd,
		cwd=root,
		check=False,
		text=True,
		capture_output=True,
	)

	if result.returncode != 0:
		log("Compiler returned a non-zero exit code.", Color.RED, "!")
		log("=== STDOUT ===", Color.WHITE)
		log(result.stdout, Color.WHITE)
		log("=== STDERR ===", Color.RED)
		log(result.stderr, Color.RED)
		sys.exit(result.returncode)

	obj_path = root / (input_file_name[:-3] + "obj")
	if obj_path.exists():
		obj_path.unlink()

	if not dll_path.is_file():
		log(
			f"ERROR: Expected DLL not found: {dll_path}",
			Color.RED,
			"!"
		)
		sys.exit(1)

	log(
		f"Encoding {dll_path.name} as Base64...",
		Color.CYAN,
		"*"
	)

	dll_bytes = dll_path.read_bytes()
	b64_str = base64.b64encode(dll_bytes).decode("ascii")

	log(
		f"Assembling {output_file_name} ...",
		Color.CYAN,
		"*"
	)

	original_text = py_path.read_text(encoding="utf-8")

	pattern = re.compile(
		r"^WRAPPED_DLL\s*=.*$",
		re.MULTILINE
	)

	replacement_line = f"WRAPPED_DLL = '{b64_str}'"

	new_text, count = pattern.subn(
		replacement_line,
		original_text
	)

	if count == 0:
		log(
			f"ERROR: No line matching 'WRAPPED_DLL = ...' "
			f"was found in {python_file_name}.",
			Color.RED,
			"!"
		)
		sys.exit(1)

	with open(
		build / output_file_name,
		"w",
		encoding="utf-8"
	) as f:
		f.write(new_text)

	try:
		dll_path.unlink()
	except OSError:
		log(
			f"Warning: could not delete {dll_path}",
			Color.YELLOW,
			"~"
		)

	log(
		f"Wrote file to build/{output_file_name}",
		Color.GREEN,
		"+"
	)
