# Composer Tools

Command-line utilities for preparing music parts for performance and distribution.

## Tools

### `part_prep.py`

Batch-processes a folder of part PDFs exported from a notation program (Sibelius, Dorico, MuseScore, Finale, etc.) into print-ready files. It does three things:

1. **Rename** — Renames exported files into score order with a consistent format: `01. MA Flute.pdf`, `02. MA Oboe.pdf`, etc.
2. **Prepend cover page** — Adds a cover page PDF to the front of each part.
3. **Stamp part name** — Prints the instrument name in bold Times 30pt on the top-right of the first page.

These can be run individually or all at once. Every operation previews its changes and asks for confirmation before writing.

## Requirements

- Python 3.8+
- [pypdf](https://pypi.org/project/pypdf/)
- [reportlab](https://pypi.org/project/reportlab/)

```
pip install pypdf reportlab
```

## Usage

```
python part_prep.py
```

The script walks you through configuration interactively:

1. Enter the composer's last name (automatically uppercased in filenames).
2. Enter the directory containing the exported PDFs (or `.` for the current directory).
3. Paste the score order, one instrument per line. Blank line to finish.
4. For each instrument, enter the text that uniquely identifies it in the original filename (e.g. `Soprano_Saxophone`, `Violin_1`).
5. Choose an action: rename, prepend cover, stamp part names, or all three in sequence.

No files are deleted. Renames use `os.rename`; cover prepend and stamping overwrite the file in place. Back up your folder first if you want to keep the originals.

## License

MIT