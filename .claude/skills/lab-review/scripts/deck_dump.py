#!/usr/bin/env python3
"""Print slide text, media and speaker notes from an unzipped .pptx, in PRESENTATION order.

    unzip -oq deck.pptx -d <dir>
    python deck_dump.py <dir> 33 44          # slides 33 to 44 as the audience sees them
    python deck_dump.py <dir> --titles       # one line per slide, for diffing two decks

Slide file names (slide37.xml) are NOT the slide order once slides have been
inserted or moved. The order lives in ppt/presentation.xml, so read it from there.
"""
import html
import os
import re
import sys


def slide_files(root):
    pres = open(os.path.join(root, "ppt/presentation.xml"), encoding="utf-8").read()
    rels = open(os.path.join(root, "ppt/_rels/presentation.xml.rels"), encoding="utf-8").read()
    by_id = {}
    for tag in re.findall(r"<Relationship [^>]*>", rels):
        rid = re.search(r'Id="(rId\d+)"', tag)
        target = re.search(r'Target="slides/(slide\d+\.xml)"', tag)
        if rid and target:
            by_id[rid.group(1)] = target.group(1)
    return [by_id[r] for r in re.findall(r'<p:sldId [^>]*r:id="(rId\d+)"', pres)]


def paragraphs(path):
    if not os.path.exists(path):
        return []
    xml = open(path, encoding="utf-8").read()
    out = []
    for p in re.findall(r"<a:p>(.*?)</a:p>", xml, flags=re.S):
        text = "".join(re.findall(r"<a:t>(.*?)</a:t>", p, flags=re.S))
        if text.strip():
            out.append(html.unescape(text))
    return out


def main():
    root = sys.argv[1]
    files = slide_files(root)
    if "--titles" in sys.argv:
        for i, f in enumerate(files, 1):
            first = paragraphs(os.path.join(root, "ppt/slides", f))
            print(f"{i}\t{(first[0] if first else '(no text)')[:80]}")
        return
    lo, hi = int(sys.argv[2]), int(sys.argv[3])
    print("slides:", len(files))
    for i, f in enumerate(files, 1):
        if not lo <= i <= hi:
            continue
        print(f"\n===== SLIDE {i} ({f})")
        print("\n".join(paragraphs(os.path.join(root, "ppt/slides", f))))
        rel_path = os.path.join(root, "ppt/slides/_rels", f + ".rels")
        rels = open(rel_path, encoding="utf-8").read() if os.path.exists(rel_path) else ""
        media = re.findall(r'Target="\.\./media/([^"]+)"', rels)
        if media:
            print("  MEDIA:", media)
        notes = re.findall(r"notesSlides/(notesSlide\d+\.xml)", rels)
        if notes:
            print("  NOTES:", "\n".join(paragraphs(os.path.join(root, "ppt/notesSlides", notes[0]))))


if __name__ == "__main__":
    main()
