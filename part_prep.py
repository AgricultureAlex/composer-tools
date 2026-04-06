#!/usr/bin/env python3
"""
Part Preparation Tool
=====================
Renames, prepends cover pages, and stamps part names onto a set of
music part PDFs exported from a notation program.

Requirements:
    pip install pypdf reportlab

Setup:
    Place a config file called part_prep_config.txt in your working
    directory (option 5 generates an example). It includes all settings:
    directory, composer, cover page, font, score order, and search strings.

    Alternatively, for interactive mode (options 1-3), place a
    score_order.txt file in the part PDF directory listing one
    instrument per line in score order.

Usage:
    python part_prep.py
"""

import os
import re
import sys
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# ── config file ──────────────────────────────────────────────────────

CONFIG_FILENAME = "part_prep_config.txt"

EXAMPLE_CONFIG = """\
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
"""


def load_config(path):
    """Parse a part_prep_config.txt file into a dict."""
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    config = {}
    # Split on --- field_name --- dividers
    sections = re.split(r"^---\s*(.+?)\s*---\s*$", raw, flags=re.MULTILINE)
    # sections = ['preamble', 'field1', 'content1', 'field2', 'content2', ...]
    for i in range(1, len(sections) - 1, 2):
        field = sections[i].strip()
        lines = [
            l.strip()
            for l in sections[i + 1].strip().splitlines()
            if l.strip() and not l.strip().startswith("#")
        ]
        if field in ("search_strings", "score_order"):
            config[field] = lines  # keep as list
        elif lines:
            config[field] = lines[0]  # single value

    return config


def generate_example_config(directory):
    """Write an example config file and exit."""
    path = os.path.join(directory, CONFIG_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        f.write(EXAMPLE_CONFIG)
    print(f"Generated example config: {path}")
    print("Edit it with your settings, then run part_prep.py again.")


def resolve_config(config, score_order):
    """Expand search_strings '=' shorthand and build the full search list."""
    raw_searches = config.get("search_strings", [])
    search_strings = []
    for i, name in enumerate(score_order):
        order = i + 1
        if i < len(raw_searches):
            s = raw_searches[i]
            if s == "=":
                s = name
        else:
            s = name
        search_strings.append((s, order, name))
    return search_strings


# ── helpers ──────────────────────────────────────────────────────────


def confirm(prompt="Proceed? (y/n): "):
    return input(prompt).strip().lower() == "y"


def numbered_part_files(directory):
    """Return sorted list of filenames matching '##. ...' in directory."""
    return sorted(
        f
        for f in os.listdir(directory)
        if f.endswith(".pdf") and re.match(r"\d{2}\.", f)
    )


def ask_directory():
    directory = input("Directory containing the part PDFs [.]: ").strip() or "."
    if not os.path.isdir(directory):
        print(f"Directory not found: {directory}")
        sys.exit(1)
    return directory


def ask_composer():
    composer = input("Composer last name (e.g. Ma): ").strip()
    if not composer:
        print("No name entered. Exiting.")
        sys.exit(1)
    composer_upper = composer.upper()
    print(f"  → Composer tag: {composer_upper}")
    return composer_upper


def load_score_order(directory):
    """Load score order from score_order.txt in the given directory."""
    path = os.path.join(directory, "score_order.txt")
    if not os.path.exists(path):
        print(f"score_order.txt not found in {directory}")
        print("Create a text file called score_order.txt with one instrument per line.")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        score_order = [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]

    if not score_order:
        print("score_order.txt is empty.")
        sys.exit(1)

    print(f"Loaded score order from {path} ({len(score_order)} parts):\n")
    for i, name in enumerate(score_order, 1):
        print(f"    {i:2d}. {name}")

    return score_order


def ask_search_strings(score_order):
    """For each instrument, ask what string to search for in the original filenames."""
    print("\nFor each instrument, enter the text that uniquely identifies it")
    print("in the ORIGINAL exported filename (e.g. Soprano_Saxophone, Violin_1).")
    print("Press Enter to use the part name as-is. Type 'b' to go back.\n")

    search_strings = []
    i = 0
    while i < len(score_order):
        name = score_order[i]
        order = i + 1
        default = search_strings[i][0] if i < len(search_strings) else name
        s = input(f'  {order:2d}. {name} → search for [Enter = "{default}"]: ').strip()

        if s.lower() == "b":
            if i > 0:
                i -= 1
                print(f"      ↩ Back to {score_order[i]}")
            else:
                print("      Already at the first instrument.")
            continue

        if not s:
            s = default

        if i < len(search_strings):
            search_strings[i] = (s, order, name)
        else:
            search_strings.append((s, order, name))
        i += 1

    if not search_strings:
        print("No search strings entered. Exiting.")
        sys.exit(1)

    return search_strings


# ── 1. rename ────────────────────────────────────────────────────────


def rename_parts(directory=None, composer=None, score_order=None, search_strings=None):
    """Rename exported part PDFs into score order.

    New names follow the format: ##. COMPOSER Part Name.pdf
    """
    directory = directory or ask_directory()
    composer = composer or ask_composer()
    if score_order is None:
        score_order = load_score_order(directory)
    if search_strings is None:
        search_strings = ask_search_strings(score_order)

    all_pdfs = [f for f in os.listdir(directory) if f.endswith(".pdf")]
    renames = []

    for search, order, part_name in search_strings:
        matches = [f for f in all_pdfs if search in f]
        if len(matches) == 1:
            old = matches[0]
            new = f"{order:02d}. {composer} {part_name}.pdf"
            renames.append((order, old, new))
        elif len(matches) == 0:
            print(f"  WARNING: No file found containing '{search}'")
        else:
            print(f"  WARNING: Multiple files match '{search}': {matches}")
            print(f"           Skipping — make the search string more specific.")

    renames.sort(key=lambda x: x[0])

    if not renames:
        print("No files matched. Nothing to rename.")
        return False

    print(f"\nPlanned renames ({len(renames)} files):\n")
    for order, old, new in renames:
        print(f"  {old}")
        print(f"  → {new}\n")

    if not confirm():
        print("Rename cancelled.")
        return False

    for _, old, new in renames:
        os.rename(os.path.join(directory, old), os.path.join(directory, new))
    print(f"Renamed {len(renames)} files.\n")
    return True


# ── 2. prepend cover ─────────────────────────────────────────────────


def prepend_cover(directory=None, cover_name=None):
    """Prepend a cover-page PDF to each numbered part file."""
    directory = directory or ask_directory()
    if not cover_name:
        cover_name = input("Cover page filename (e.g. Cover Page.pdf): ").strip()
    if not cover_name:
        print("No filename entered. Skipping cover prepend.")
        return False

    cover_path = os.path.join(directory, cover_name)
    if not os.path.exists(cover_path):
        print(f"File not found: {cover_path}")
        return False

    cover_reader = PdfReader(cover_path)
    print(f"Cover PDF has {len(cover_reader.pages)} page(s).\n")

    part_files = [f for f in numbered_part_files(directory) if f != cover_name]

    if not part_files:
        print("No numbered part files found.")
        return False

    print(f"Will prepend cover to {len(part_files)} file(s):\n")
    for f in part_files:
        print(f"  {f}")

    print()
    if not confirm():
        print("Cover prepend cancelled.")
        return False

    for filename in part_files:
        filepath = os.path.join(directory, filename)
        part_reader = PdfReader(filepath)
        writer = PdfWriter()

        for page in cover_reader.pages:
            writer.add_page(page)
        for page in part_reader.pages:
            writer.add_page(page)

        with open(filepath, "wb") as out:
            writer.write(out)
        print(f"  Done: {filename}")

    print(f"\nPrepended cover to {len(part_files)} files.\n")
    return True


# ── 3. stamp part names ──────────────────────────────────────────────


def _register_font(font_path):
    """Register a TTF font file and return its ReportLab name."""
    font_name = os.path.splitext(os.path.basename(font_path))[0]
    try:
        pdfmetrics.getFont(font_name)
    except KeyError:
        pdfmetrics.registerFont(TTFont(font_name, font_path))
    return font_name


def _create_text_overlay(
    text, page_width, page_height, font_name="Times-Bold", font_size=12
):
    """Create a one-page PDF with text at the top-right corner."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_width, page_height))

    margin_right = 36  # 0.5 in
    margin_top = 36  # 0.5 in

    c.setFont(font_name, font_size)
    text_width = c.stringWidth(text, font_name, font_size)

    x = page_width - margin_right - text_width
    y = page_height - margin_top - font_size

    c.drawString(x, y, text)
    c.save()
    buf.seek(0)
    return buf


def _extract_part_name(filename):
    """Extract part name from '##. COMPOSER Part Name.pdf'."""
    name = filename.rsplit(".pdf", 1)[0]
    match = re.match(r"\d{2}\.\s+\S+\s+(.+)$", name)
    return match.group(1).strip() if match else None


def stamp_part_names(directory=None, font_path=None, font_size=None):
    """Add the part name to the top-right of page 1 using a user-specified font."""
    directory = directory or ask_directory()

    # Font configuration
    if font_path is None:
        print("Font setup:")
        font_path = input(
            "  Path to .ttf font file [leave blank for Times-Bold]: "
        ).strip()

    if font_path:
        font_path = os.path.expanduser(font_path)
        if not os.path.exists(font_path):
            print(f"  Font file not found: {font_path}")
            return False
        font_name = _register_font(font_path)
        print(f"  → Registered font: {font_name}")
    else:
        font_name = "Times-Bold"
        print(f"  → Using built-in: {font_name}")

    if font_size is None:
        size_input = input("  Font size in pt [12]: ").strip()
        font_size = int(size_input) if size_input else 12
    print(f"  → Size: {font_size}pt\n")

    part_files = numbered_part_files(directory)
    if not part_files:
        print("No numbered part files found.")
        return False

    plan = []
    print(f"Found {len(part_files)} file(s):\n")
    for f in part_files:
        part_name = _extract_part_name(f)
        if part_name:
            plan.append((f, part_name))
            print(f'  {f}  →  "{part_name}"')
        else:
            print(f"  {f}  →  [SKIPPED: could not extract part name]")

    if not plan:
        print("\nNo files to process.")
        return False

    print()
    if not confirm("Add part names to these files? (y/n): "):
        print("Stamp cancelled.")
        return False

    for filename, part_name in plan:
        filepath = os.path.join(directory, filename)
        reader = PdfReader(filepath)
        writer = PdfWriter()

        for i, page in enumerate(reader.pages):
            if i == 0:
                box = page.mediabox
                pw, ph = float(box.width), float(box.height)
                overlay_buf = _create_text_overlay(
                    part_name, pw, ph, font_name, font_size
                )
                overlay_page = PdfReader(overlay_buf).pages[0]
                page.merge_page(overlay_page)
            writer.add_page(page)

        with open(filepath, "wb") as out:
            writer.write(out)
        print(f"  Done: {filename}")

    print(f"\nStamped part names on {len(plan)} files.\n")
    return True


# ── 4. all-in-one ─────────────────────────────────────────────────────


def all_in_one_interactive():
    """Run rename → prepend cover → stamp part names (interactive prompts)."""
    directory = ask_directory()
    composer = ask_composer()
    score_order = load_score_order(directory)
    search_strings = ask_search_strings(score_order)

    print("\n── Step 1/3: Rename ──\n")
    if not rename_parts(directory, composer, score_order, search_strings):
        if not confirm("Rename did not complete. Continue anyway? (y/n): "):
            return

    print("\n── Step 2/3: Prepend Cover Page ──\n")
    if not prepend_cover(directory):
        if not confirm("Cover prepend did not complete. Continue anyway? (y/n): "):
            return

    print("\n── Step 3/3: Stamp Part Names ──\n")
    stamp_part_names(directory)

    print("\n" + "=" * 60)
    print("  All done!")
    print("=" * 60)


def all_in_one_from_config(config):
    """Run rename → prepend cover → stamp part names from config file."""
    directory = config.get("directory", ".")
    directory = os.path.expanduser(directory)
    if not os.path.isdir(directory):
        print(f"Directory not found: {directory}")
        return

    composer = config.get("composer", "").upper()
    if not composer:
        print("No composer specified in config. Exiting.")
        return
    print(f"Composer tag: {composer}")

    score_order = config.get("score_order")
    if score_order:
        print(f"\nScore order from config ({len(score_order)} parts):\n")
        for i, name in enumerate(score_order, 1):
            print(f"    {i:2d}. {name}")
    else:
        score_order = load_score_order(directory)
    search_strings = resolve_config(config, score_order)

    cover_name = config.get("cover_page", "")
    font_path = config.get("font_path", "")
    font_size_str = config.get("font_size", "12")
    font_size = int(font_size_str) if font_size_str else 12

    print("\n── Step 1/3: Rename ──\n")
    if not rename_parts(directory, composer, score_order, search_strings):
        if not confirm("Rename did not complete. Continue anyway? (y/n): "):
            return

    print("\n── Step 2/3: Prepend Cover Page ──\n")
    if cover_name:
        if not prepend_cover(directory, cover_name):
            if not confirm("Cover prepend did not complete. Continue anyway? (y/n): "):
                return
    else:
        print("No cover_page in config. Skipping.")

    print("\n── Step 3/3: Stamp Part Names ──\n")
    stamp_part_names(directory, font_path, font_size)

    print("\n" + "=" * 60)
    print("  All done!")
    print("=" * 60)


# ── main menu ─────────────────────────────────────────────────────────


def main():
    print("=" * 60)
    print("  Part Preparation Tool")
    print("=" * 60)
    print()
    print("  1. Rename files into score order")
    print("  2. Prepend a cover page to each part")
    print("  3. Stamp part names on page 1 (top-right, custom font)")
    print("  4. All of the above (1 → 2 → 3)")
    print("  5. Generate example config file")
    print()

    choice = input("Choose [1/2/3/4/5]: ").strip()
    print()

    if choice == "5":
        directory = input("Directory for config file [.]: ").strip() or "."
        generate_example_config(directory)
        return

    # Check for config file in current directory
    config = None
    if choice == "4":
        # Look for config in . first, then ask
        for candidate in [".", os.getcwd()]:
            cfg_path = os.path.join(candidate, CONFIG_FILENAME)
            if os.path.exists(cfg_path):
                print(f"Found config: {cfg_path}")
                if confirm("Use this config file? (y/n): "):
                    config = load_config(cfg_path)
                    print(f"  Loaded {len(config)} fields from config.\n")
                break

    if choice == "1":
        rename_parts()
    elif choice == "2":
        prepend_cover()
    elif choice == "3":
        stamp_part_names()
    elif choice == "4":
        if config:
            all_in_one_from_config(config)
        else:
            all_in_one_interactive()
    else:
        print("Invalid choice.")


if __name__ == "__main__":
    main()
