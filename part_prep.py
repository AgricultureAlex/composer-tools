#!/usr/bin/env python3
"""
Part Preparation Tool
=====================
Renames, prepends cover pages, and stamps part names onto a set of
music part PDFs exported from a notation program.

Requirements:
    pip install pypdf reportlab

Setup:
    Place a file called score_order.txt in the same directory as your
    part PDFs, listing one instrument per line in score order. E.g.:

        Flute
        Oboe
        Clarinet in B♭

    Lines starting with # and blank lines are ignored.

Usage:
    python part_prep.py

You will be prompted to choose one of four actions:
    1. Rename       — Rename exported PDFs into score order
    2. Cover        — Prepend a cover-page PDF to each part
    3. Stamp        — Add the part name (top-right, custom font) to page 1
    4. All-in-one   — Run 1 → 2 → 3 in sequence

Only the inputs relevant to your chosen action are collected.
"""

import os
import re
import sys
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

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
    """Load score order from score_order.txt in the given directory.

    The file should list one instrument per line, e.g.:
        Flute
        Oboe
        Clarinet in B♭
        ...

    Blank lines and lines starting with # are ignored.
    """
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
    print("Press Enter to use the part name as-is. Type '/b' to go back.\n")

    search_strings = []  # list of (search, order_num, part_name)
    i = 0
    while i < len(score_order):
        name = score_order[i]
        order = i + 1
        default = search_strings[i][0] if i < len(search_strings) else name
        s = input(f'  {order:2d}. {name} → search for [Enter = "{default}"]: ').strip()

        if s.lower() == "/b":
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


def prepend_cover(directory=None):
    """Prepend a cover-page PDF to each numbered part file."""
    directory = directory or ask_directory()

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
    # Derive a ReportLab name from the filename (e.g. "Cardo-Bold.ttf" -> "Cardo-Bold")
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


def stamp_part_names(directory=None):
    """Add the part name to the top-right of page 1 using a user-specified font."""
    directory = directory or ask_directory()

    # Font configuration
    print("Font setup:")
    font_path = input("  Path to .ttf font file [leave blank for Times-Bold]: ").strip()
    if font_path:
        if not os.path.exists(font_path):
            print(f"  Font file not found: {font_path}")
            return False
        font_name = _register_font(font_path)
        print(f"  → Registered font: {font_name}")
    else:
        font_name = "Times-Bold"
        print(f"  → Using built-in: {font_name}")

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


def all_in_one():
    """Run rename → prepend cover → stamp part names in sequence."""
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
    print()

    choice = input("Choose [1/2/3/4]: ").strip()
    print()

    if choice == "1":
        rename_parts()
    elif choice == "2":
        prepend_cover()
    elif choice == "3":
        stamp_part_names()
    elif choice == "4":
        all_in_one()
    else:
        print("Invalid choice.")


if __name__ == "__main__":
    main()
