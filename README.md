# For Composers
Please watch the [`Tutorial Video.mp4` video demo](https://youtu.be/7cNrmuOes8E).

# Composer Tools

Command-line utilities for preparing music parts for performance and distribution.

## Tools

### `part_prep.py`

Batch-processes a folder of part PDFs exported from a notation program (Sibelius, Dorico, MuseScore, Finale, etc.) into print-ready files.

It does three things, individually or all at once:

1. **Copy & rename** — Copies exported files into a separate output folder, renamed into score order: `01. MA Flute.pdf`, `02. MA Oboe.pdf`, etc.
2. **Prepend cover page** — Adds a cover page PDF to the front of each part, with optional blank pages after the cover (useful for planned page turns).
3. **Stamp part name** — Prints the instrument name on the top-right of the first page using a font and size you specify.

Originals are never touched — step 1 copies into a fresh `outputs_go_here` folder, and steps 2 and 3 operate on those copies in place.

## Requirements

Python 3.8+ and two packages:

```
pip install pypdf reportlab
```

A font file is needed for the stamp step if you want characters like ♭ or ♯ (the built-in Times-Bold doesn't support them). [Cardo](https://fonts.google.com/specimen/Cardo) is bundled in this repo and is the default in the example config.

**Accidental fallback fonts.** Because most text fonts (including Cardo) don't include ♭ and ♯ glyphs, the script automatically falls back to a music-friendly font for those characters. It looks for Edwin or Leland under `./fonts/` by default — both are bundled. If you want to use your own font, move the downloaded folder/file to `./fonts` and run the following

```
pip install afdko
otf2ttf fonts/YourFont/YourFontFile.otf
```

ReportLab's font loader only handles real TrueType outlines, so this one-time conversion is required for any CFF-flavored font.

## Quick Start

1. Export your parts from your notation program into a folder. Or, use the provided example files from _Pelagic_.

2. Generate a config file:

```
python part_prep.py
→ choose 5
```

This creates `part_prep_config.txt` in the directory you specify.

3. Edit `part_prep_config.txt`. For the example files, everything is already set up — you can experiment by copying fresh parts from `example_backups` between runs. The default (_Pelagic_) config file looks like this:

```
# Part Preparation Tool — Config File
# ====================================
# Fill in the fields below. Lines starting with # are ignored.
# To regenerate this file, delete it and run part_prep.py.

--- parts directory ---
# Path to the folder containing the exported part PDFs.
./your_parts_here

--- composer ---
Ma

--- cover_page ---
./your_front_matter_here/Pelagic (Part) Cover Page.pdf

--- blank_pages_after_cover ---
# Number of blank pages to insert after the cover and before the part.
# This is the global default; per-part overrides go in search_strings below.
0

--- blank_page ---
# PDF whose first page is used as the blank page. If omitted or missing,
# a procedural blank sized to the cover is used as a fallback.
./your_front_matter_here/letter_blank_page.pdf

--- font_path ---
# If you're OK with boldface Cardo, you can leave this unchanged.
./fonts/cardo/Cardo-Bold.ttf

--- font_size ---
# If you're OK with font size 18, you can leave this unchanged.
18

--- search_strings ---
# One mapping per line. The order of lines here defines the output score order (!!!).
# Format:
#   input -> file_name / stamp_name + extra_blank_pages
#   input -> stamp_name + extra_blank_pages
#   input -> stamp_name
#   input
#
# file_name        = the name used in the output filename (defaults to stamp_name)
# stamp_name       = the text stamped on page 1 (defaults to input)
# extra_blank_pages = blank pages inserted after cover for this part (defaults to 0)
#
# Examples:
#     Soprano_Saxophone -> Sx / Soprano Saxophone + 3
#         (file renamed using "Sx", stamped "Soprano Saxophone", 3 extra blank pages)
#     Soprano_Saxophone -> Soprano Saxophone + 1
#         (file renamed/stamped "Soprano Saxophone", 1 extra blank page)
#     Soprano_Saxophone -> Soprano Saxophone
#         (file renamed/stamped "Soprano Saxophone", 0 extra blank pages)
#     Soprano_Saxophone
#         (all values default to the search string, 0 extra blank pages)
Flute -> Flute
Oboe -> Oboe
Clarinet -> Cl / Clarinet in B♭
Soprano_Saxophone -> Sx / Soprano Saxophone + 3
Bassoon -> Bassoon
Vibraphone -> Vibraphone
Harp -> Harp
Piano -> Piano
Violin_1 -> Violin 1
Violin_2 -> Violin 2
Viola -> Viola
Violoncello -> Violoncello
Contrabass -> Db / Double Bass
```

Each `--- field ---` divider marks a section. Lines starting with `#` and blank lines are ignored.

The fields:

| Field | What it does |
|---|---|
| `parts directory` | Path to the folder containing the exported PDFs |
| `composer` | Last name, automatically uppercased in filenames |
| `cover_page` | Path to the cover page PDF (resolved from the script's working directory) |
| `blank_pages_after_cover` | Global default number of blank pages to insert after the cover; can be overridden per part |
| `blank_page` | Path to a PDF whose first page is used as the blank page (optional — falls back to a procedural blank if omitted) |
| `font_path` | Path to a font file for the stamp step (TrueType outlines only — see Requirements) |
| `font_size` | Font size in points for the stamp step |
| `search_strings` | One mapping per line. The **order of these lines defines the output score order.** Each line uses the format described below. |

#### Search string format

Each line in `search_strings` maps an input filename pattern to a renamed output and a stamped label. There are four supported forms:

```
input -> file_name / stamp_name + extra_blank_pages
input -> stamp_name + extra_blank_pages
input -> stamp_name
input
```

- **`input`** — text that uniquely identifies the part in the original exported filename (e.g. `Soprano_Saxophone`).
- **`file_name`** — short name used in the output filename (e.g. `Sx`). Defaults to `stamp_name`.
- **`stamp_name`** — full label printed on page 1 (e.g. `Soprano Saxophone`). Defaults to `input`. Supports ♭ and ♯ via the accidental fallback font.
- **`extra_blank_pages`** — per-part override for blank pages after the cover. Defaults to 0. Useful for planned page turns.

Examples:

```
Soprano_Saxophone -> Sx / Soprano Saxophone + 3
Clarinet -> Cl / Clarinet in B♭
Violin_1 -> Violin 1 + 1
Flute
```

4. Run the all-in-one pipeline:

```
python part_prep.py
→ choose 4
→ confirm the config file when prompted
```

It runs copy/rename → cover → stamp in sequence, confirming before each step. Output files land in `outputs_go_here/` next to the script.

## Interactive Mode - NO LONGER SUPPORTED

Options 1–3 run individual steps with interactive prompts instead of the config file. These use a separate `score_order.txt` file (one instrument per line) placed in the parts directory.

- **Option 1 (Copy & Rename)** — asks for directory, composer name, loads `score_order.txt`, then prompts for search-string mappings one by one. Press Enter to accept the default; type `b` to go back and fix a previous entry. Each prompt accepts the full `input -> file_name / stamp_name + extra_blank_pages` format.
- **Option 2 (Cover)** — asks for directory, cover page path, global blank-page count, and an optional blank-page PDF.
- **Option 3 (Stamp)** — asks for directory, font path, and font size.

## License

MIT
