#!/usr/bin/env python3
"""Record a prototype demo as silent video, sized to a target duration.

The flow is JSON-described — the skill writes a flow file matching the
prototype's specific buttons and inputs, and this script executes it.
Dwell times are auto-scaled to hit the target duration.

Usage:
  python record_demo.py --url https://example.com/search \\
                        --flow flow.json \\
                        --duration 37 \\
                        --output prototype.webm

flow.json schema:
{
  "steps": [
    {"action": "wait", "ms": 2000},
    {"action": "click", "selector": "button:has-text('Search')"},
    {"action": "type", "selector": "input[type=text]", "text": "moody lo-fi"},
    {"action": "press", "key": "Enter"},
    {"action": "scroll", "y": 320},
    {"action": "navigate_back"},
    {"action": "screenshot_dwell", "ms": 3000}
  ]
}
"""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def execute_flow(page, steps, dwell_scale: float = 1.0):
    """Run a flow described as a list of step dicts. Returns nothing."""
    for step in steps:
        a = step["action"]
        if a == "wait":
            page.wait_for_timeout(int(step["ms"] * dwell_scale))
        elif a == "click":
            page.locator(step["selector"]).first.click()
            page.wait_for_timeout(int(step.get("after_ms", 800) * dwell_scale))
        elif a == "type":
            loc = page.locator(step["selector"]).first
            loc.click()
            page.keyboard.type(step["text"], delay=step.get("delay", 60))
            page.wait_for_timeout(int(step.get("after_ms", 600) * dwell_scale))
        elif a == "press":
            page.keyboard.press(step["key"])
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(int(step.get("after_ms", 2000) * dwell_scale))
        elif a == "scroll":
            page.mouse.wheel(0, step["y"])
            page.wait_for_timeout(int(step.get("after_ms", 1500) * dwell_scale))
        elif a == "navigate_back":
            page.go_back()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(int(step.get("after_ms", 1500) * dwell_scale))
        elif a == "navigate":
            page.goto(step["url"], wait_until="networkidle")
            page.wait_for_timeout(int(step.get("after_ms", 1500) * dwell_scale))
        elif a == "screenshot_dwell":
            page.wait_for_timeout(int(step["ms"] * dwell_scale))
        else:
            print(f"  warn: unknown action {a}")


def record(url: str, flow_path: str, output_path: Path, duration: float = None,
           viewport=(1920, 1080)):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    flow = json.loads(Path(flow_path).read_text()) if flow_path else {"steps": []}
    steps = flow["steps"]

    # If we have a target duration, estimate the natural duration from the flow
    # and scale dwell times to match.
    dwell_scale = 1.0
    if duration:
        natural_ms = sum(
            s.get("ms", 0) +
            s.get("after_ms", {"click": 800, "type": 600, "press": 2000,
                               "scroll": 1500, "navigate_back": 1500,
                               "navigate": 1500, "screenshot_dwell": 0,
                               "wait": 0}.get(s["action"], 0))
            for s in steps
        )
        # Add a per-step typing-time estimate so scale isn't dominated by dwells
        type_ms = sum(len(s.get("text", "")) * s.get("delay", 60)
                      for s in steps if s["action"] == "type")
        natural_ms += type_ms
        if natural_ms > 0:
            dwell_scale = (duration * 1000) / natural_ms
            print(f"  natural duration ≈ {natural_ms/1000:.1f}s, "
                  f"target {duration}s, dwell_scale = {dwell_scale:.3f}")

    record_dir = output_path.parent / "_record_tmp"
    record_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]},
            record_video_dir=str(record_dir),
            record_video_size={"width": viewport[0], "height": viewport[1]},
        )
        page = ctx.new_page()

        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(int(2000 * dwell_scale))

        execute_flow(page, steps, dwell_scale)

        page.close()
        ctx.close()
        browser.close()

    # Find the produced webm and rename to output_path
    webms = list(record_dir.glob("*.webm"))
    if not webms:
        raise RuntimeError("playwright did not produce a video file")
    if output_path.exists():
        output_path.unlink()
    webms[0].rename(output_path)

    # cleanup tmp dir
    for f in record_dir.glob("*"):
        f.unlink()
    record_dir.rmdir()

    print(f"  saved → {output_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", required=True)
    ap.add_argument("--flow",
                    help="path to flow.json (if omitted, just records the landing page idle)")
    ap.add_argument("--duration", type=float,
                    help="target duration in seconds (dwells auto-scale)")
    ap.add_argument("--output", required=True)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    args = ap.parse_args()

    record(args.url, args.flow, Path(args.output), args.duration,
           (args.width, args.height))


if __name__ == "__main__":
    main()
