#!/usr/bin/env python3
"""Capture each slide of an HTML deck as a 1920×1080 PNG.

The deck is expected to support keyboard navigation (right-arrow advances).
That convention matches the output of the `frontend-design` skill and most
common deck templates.

Usage:
  python capture_slides.py --deck presentation/index.html --output slides/
  python capture_slides.py --deck https://example.com/deck.html --output slides/ --count 7
"""
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


def capture(deck_url: str, output_dir: Path, count: int, viewport=(1920, 1080)):
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]},
            device_scale_factor=2,  # crisper PNGs
        )
        page = ctx.new_page()

        # accept either a file path or a URL
        if deck_url.startswith("http"):
            url = deck_url
        else:
            p_path = Path(deck_url).resolve()
            url = f"file://{p_path}"

        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(1200)  # let webfonts load

        for i in range(1, count + 1):
            if i > 1:
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(700)  # transitions + reveals
            out = output_dir / f"slide_{i:02d}.png"
            page.screenshot(path=str(out), full_page=False)
            print(f"  → {out}")

        browser.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--deck", required=True,
                    help="path or URL to the HTML deck")
    ap.add_argument("--output", required=True,
                    help="directory to write slide_NN.png files into")
    ap.add_argument("--count", type=int, default=7,
                    help="number of slides to capture (default: 7)")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    args = ap.parse_args()

    capture(args.deck, Path(args.output), args.count, (args.width, args.height))
    print(f"done — {args.count} slides → {args.output}")


if __name__ == "__main__":
    main()
