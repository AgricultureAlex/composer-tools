# Composer Tools

Command-line utilities for preparing music parts for performance and distribution.

## Tools

### `part_prep.py`

Batch-processes a folder of part PDFs exported from a notation program (Sibelius, Dorico, MuseScore, Finale, etc.) into print-ready files.

It does three things, individually or all at once:

1. **Rename** — Renames exported files into score order: `01. MA Flute.pdf`, `02. MA Oboe.pdf`, etc.
2. **Prepend cover page** — Adds a cover page PDF to the front of each part.
3. **Stamp part name** — Prints the instrument name on the top-right of the first page using a font and size you specify.

No files are deleted. Renames use `os.rename`; cover prepend and stamping overwrite in place. Back up your folder first if you want to keep the originals.

## Requirements

Python 3.8+ and two packages:

```
pip install pypdf reportlab
```

A `.ttf` font file is needed for the stamp step if you want characters like ♭ or ♯ (the built-in Times-Bold doesn't support them). [Cardo](https://fonts.google.com/specimen/Cardo) works well.

## Quick Start

1. Export your parts from your notation program into a folder.

2. Generate a config file:

```
python part_prep.py
→ choose 5
```

This creates `part_prep_config.txt` in the directory you specify.

3. Edit `part_prep_config.txt`. It looks like this:

```
--- directory ---
.

--- composer ---
Ma

--- cover_page ---
Pelagic (Part) Cover Page.pdf

--- font_path ---
~/Library/Fonts/Cardo-Bold.ttf

--- font_size ---
12

--- score_order ---
Flute
Oboe
Clarinet in B♭
Soprano Saxophone
Bassoon

--- search_strings ---
Flute
Oboe
Clarinet_in_Bb
Soprano_Saxophone
Bassoon
```

Each `--- field ---` divider marks a section. Lines starting with `#` and blank lines are ignored.

The fields:

| Field | What it does |
|---|---|
| `directory` | Path to the folder containing the exported PDFs |
| `composer` | Last name, automatically uppercased in filenames |
| `cover_page` | Filename of the cover page PDF (in the same directory) |
| `font_path` | Path to a `.ttf` font for the stamp step |
| `font_size` | Font size in points for the stamp step |
| `score_order` | One instrument per line, in the order they appear in the score |
| `search_strings` | One per line, same order as `score_order` — the text that uniquely identifies each part in the original exported filename. Use `=` if it matches the score order name exactly |

4. Run the all-in-one pipeline:

```
python part_prep.py
→ choose 4
→ confirm the config file when prompted
```

It runs rename → cover → stamp in sequence, confirming before each step.

## Interactive Mode

Options 1–3 run individual steps with interactive prompts instead of the config file. These use a separate `score_order.txt` file (one instrument per line) placed in the parts directory.

- **Option 1 (Rename)** — asks for directory, composer name, loads `score_order.txt`, then prompts for search strings one by one. Press Enter to use the instrument name as-is; type `b` to go back and fix a previous entry.
- **Option 2 (Cover)** — asks for directory and cover page filename.
- **Option 3 (Stamp)** — asks for directory, font path, and font size.

## License

MIT
