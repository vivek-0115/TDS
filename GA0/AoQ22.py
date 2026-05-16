import csv
import zipfile
from pathlib import Path

# ZIP file name
ZIP_FILE = "GA0/q-unicode-data.zip"

# Extract folder
EXTRACT_DIR = "unicode_data"

# Symbols to match
TARGET_SYMBOLS = {"‹", "”", "‚"}

# Total sum
total = 0

# Extract ZIP
with zipfile.ZipFile(ZIP_FILE, 'r') as zip_ref:
    zip_ref.extractall(EXTRACT_DIR)

base = Path(EXTRACT_DIR)

# File configurations
files = [
    ("data1.csv", "cp1252", ","),   # CP-1252 CSV
    ("data2.csv", "utf-8", ","),    # UTF-8 CSV
    ("data3.txt", "utf-16", "\t"),  # UTF-16 TSV
]

for filename, encoding, delimiter in files:
    path = base / filename

    with open(path, "r", encoding=encoding, newline='') as f:
        reader = csv.reader(f, delimiter=delimiter)

        for row in reader:
            if len(row) < 2:
                continue

            symbol = row[0].strip()
            value = row[1].strip()

            if symbol in TARGET_SYMBOLS:
                total += float(value)

print("Sum =", total)