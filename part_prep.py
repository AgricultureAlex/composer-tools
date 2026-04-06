#!/usr/bin/env python3
"""
Part Preparation Tool
=====================
Renames, prepends cover pages, and stamps part names onto a set of
music part PDFs exported from a notation program.

Requirements:
    pip install pypdf reportlab

Usage:
    python part_prep.py

You will be prompted to choose one of four actions:
    1. Rename       — Rename exported PDFs into score order
    2. Cover        — Prepend a cover-page PDF to each part
    3. Stamp        — Add the part name (bold, top-right) to page 1
    4. All-in-one   — Run 1 → 2 → 3 in sequence
"""

import os
import re
import sys
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas


# ── helpers ──────────────────────────────────────────────────────────

def confirm(prompt="Proceed? (y/n): "):
    return input(prompt).strip().lower() == "y"


def numbered_part_files(directory):
    """Return sorted list of filenames matching '##. ...' in directory."""
    return sorted(
        f for f in os.listdir(directory)
        if f.endswith(".pdf") and re.match(r"\d{2}\.", f)
    )


def collect_config():
    """Collect all user inputs needed for the full pipeline."""
    print("=" * 60)
    print("  Part Preparation Tool — Configuration")
    print("=" * 60)

    composer = input("\nComposer last name (e.g. Ma): ").strip()
    if not composer:
        print("No name entered. Exiting.")
        sys.exit(1)
    composer_upper = composer.upper()
    print(f"  → Composer tag: {composer_upper}")

    directory = input("\nDirectory containing the part PDFs [.]: ").strip() or "."
    if not os.path.isdir(directory):
        print(f"Directory not found: {directory}")
        sys.exit(1)

    print("\nPaste the score order below, one instrument per line.")
    print("Press Enter on an empty line when done.\n")
    print("Example:")
    print("  Flute")
    print("  Oboe")
    print("  Clarinet in B♭")
    print("  ...\n")

    score_order = []
    while True:
        line = input("  > ").strip()
        if not line:
            break
        score_order.append(line)

    if not score_order:
        print("No instruments entered. Exiting.")
        sys.exit(1)

    print(f"\n  Score order ({len(score_order)} parts):")
    for i, name in enumerate(score_order, 1):
        print(f"    {i:2d}. {name}")

    print("\nNow enter the search string that appears in the ORIGINAL filename")
    print("for each instrument — the text that uniquely identifies each part")
    print("in the files your notation software exported.\n")
    print("Enter them in the SAME ORDER as the score order above.\n")

    search_strings = []
    for i, name in enumerate(score_order, 1):
        s = input(f"  {i:2d}. {name} → search for: ").strip()
        if not s:
            print(f"  Skipping — no search string for '{name}'.")
            continue
        search_strings.append((s, i, name))

    if not search_strings:
        print("No search strings entered. Exiting.")
        sys.exit(1)

    return {
        "composer": composer_upper,
        "directory": directory,
        "score_order": score_order,
        "search_strings": search_strings,  # [(search, order_num, part_name), ...]
    }


# ── 1. rename ────────────────────────────────────────────────────────

def rename_parts(config):
    """Rename exported part PDFs into score order.

    Original files are matched by the user-provided search strings.
    New names follow the format: ##. COMPOSER Part Name.pdf
    """
    directory = config["directory"]
    composer = config["composer"]
    search_strings = config["search_strings"]

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
            print(f"           Skipping — please make the search string more specific.")

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

def prepend_cover(config):
    """Prepend a cover-page PDF to each numbered part file."""
    directory = config["directory"]

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

def _create_text_overlay(text, page_width, page_height):
    """Create a one-page PDF with text in bold Times 30pt, top-right."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_width, page_height))

    font_name = "Times-Bold"
    font_size = 30
    margin_right = 36   # 0.5 in
    margin_top = 36     # 0.5 in

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


def stamp_part_names(config):
    """Add the part name in bold Times 30pt to the top-right of page 1."""
    directory = config["directory"]

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
            print(f"  {f}  →  \"{part_name}\"")
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
                overlay_buf = _create_text_overlay(part_name, pw, ph)
                overlay_page = PdfReader(overlay_buf).pages[0]
                page.merge_page(overlay_page)
            writer.add_page(page)

        with open(filepath, "wb") as out:
            writer.write(out)
        print(f"  Done: {filename}")

    print(f"\nStamped part names on {len(plan)} files.\n")
    return True


# ── 4. all-in-one ─────────────────────────────────────────────────────

def all_in_one(config):
    """Run rename → prepend cover → stamp part names in sequence."""
    print("\n── Step 1/3: Rename ──\n")
    if not rename_parts(config):
        if not confirm("Rename did not complete. Continue anyway? (y/n): "):
            return

    print("\n── Step 2/3: Prepend Cover Page ──\n")
    if not prepend_cover(config):
        if not confirm("Cover prepend did not complete. Continue anyway? (y/n): "):
            return

    print("\n── Step 3/3: Stamp Part Names ──\n")
    stamp_part_names(config)

    print("\n" + "=" * 60)
    print("  All done!")
    print("=" * 60)


# ── main menu ─────────────────────────────────────────────────────────

def main():
    config = collect_config()

    print("\n" + "=" * 60)
    print("  What would you like to do?")
    print("=" * 60)
    print("  1. Rename files into score order")
    print("  2. Prepend a cover page to each part")
    print("  3. Stamp part names on page 1 (top-right, bold)")
    print("  4. All of the above (1 → 2 → 3)")
    print()

    choice = input("Choose [1/2/3/4]: ").strip()

    if choice == "1":
        rename_parts(config)
    elif choice == "2":
        prepend_cover(config)
    elif choice == "3":
        stamp_part_names(config)
    elif choice == "4":
        all_in_one(config)
    else:
        print("Invalid choice.")


if __name__ == "__main__":
    main()
