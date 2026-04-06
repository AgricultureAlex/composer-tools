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

A `.ttf` font file is needed for the stamp step if you want characters like ♭ or ♯ (the built-in Times-Bold doesn't support them). [Cardo](https://fonts.google.com/specimen/Cardo) is in this repo and is used as the default in the config file.

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
# Part Preparation Tool — Config File
# ====================================
# Fill in the fields below. Lines starting with # are ignored.
# To regenerate this file, delete it and run part_prep.py.

--- directory ---
/Users/alexma/Library/Mobile Documents/com~apple~CloudDocs/0 Scores Post 2022/2026/Pelagic/0 Parts Finals

--- composer ---
Ma

--- cover_page ---
Pelagic (Part) Cover Page.pdf

--- font_path ---
./Fonts/cardo/Cardo-Bold.ttf

--- font_size ---
18

--- score_order ---
# One instrument per line, in score order.
Flute
Oboe
Clarinet in B♭
Soprano Saxophone
Bassoon
Vibraphone
Harp
Piano
Violin 1
Violin 2
Viola
Violoncello
Double Bass

--- search_strings ---
# One per line, in the same order as score_order.txt.
# Use the text that uniquely identifies each part in the
# ORIGINAL exported filename. If it matches the name in
# score_order.txt exactly, you can write: =
#
# Example (for a score_order.txt with Flute / Oboe / Clarinet in Bb):
#   Flute
#   Oboe
#   Clarinet_in_Bb
#
# The = shorthand means "same as the score_order.txt name":
#   =
#   =
#   Clarinet_in_Bb
Flute
Oboe
Clarinet
Soprano Saxophone
Bassoon
Vibraphone
Harp
Piano
Violin_1
Violin_2
Viola
Violoncello
Contrabass
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
