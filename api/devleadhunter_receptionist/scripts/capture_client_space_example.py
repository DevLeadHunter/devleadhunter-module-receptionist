"""
Capture the example client space for the demo page's « Vous gardez la main » figure.

Run it with the demo host and the API up (``python scripts/capture_client_space_example.py``): it opens
``<demo host>/client/exemple`` on a wide screen, on its home dashboard, and writes the WebP the
demo page shows (``demo-host/public/showroom/espace-client.webp``). Run it again whenever the space changes.
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

_ROOT = Path(__file__).resolve().parent.parent
_OUTPUT = _ROOT.parent / "demo-host" / "public" / "showroom" / "espace-client.webp"
# The wide layout (sections, figures, chart, panels) at the proportions the demo page reserves for it (1400 × 875).
_VIEWPORT_WIDTH = 1280
_VIEWPORT_HEIGHT = 800
_OUTPUT_WIDTH = 1400
_WEBP_QUALITY = 84


def capture(demo_host_base_url: str, output: Path) -> Path:
    """
    Screenshot the example space's home on a wide screen at 2x, and write it as a WebP.

    Args:
        demo_host_base_url: The demo host serving ``/client/exemple``.
        output: Where the WebP goes.

    Returns:
        The written path.
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(
            viewport={"width": _VIEWPORT_WIDTH, "height": _VIEWPORT_HEIGHT}, device_scale_factor=2, locale="fr-FR"
        )
        page.goto(f"{demo_host_base_url.rstrip('/')}/client/exemple", wait_until="networkidle")
        page.wait_for_selector(".cs-home .cs-chart")
        # The example banner is for the visitor, not for the picture; the sidebar's portrait must be loaded.
        page.add_style_tag(content=".cs-example{display:none !important}")
        page.wait_for_timeout(600)
        png = page.screenshot(clip={"x": 0, "y": 0, "width": _VIEWPORT_WIDTH, "height": _VIEWPORT_HEIGHT})
        browser.close()
    with Image.open(io.BytesIO(png)) as image:
        ratio = _OUTPUT_WIDTH / image.width
        resized = image.convert("RGB").resize((_OUTPUT_WIDTH, round(image.height * ratio)), Image.Resampling.LANCZOS)
        output.parent.mkdir(parents=True, exist_ok=True)
        resized.save(output, format="WEBP", quality=_WEBP_QUALITY, method=6)
    return output


def main() -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Capture the example client space for the demo page.")
    parser.add_argument("--demo-host", default="http://localhost:3001", help="Demo host base URL")
    parser.add_argument("--output", default=str(_OUTPUT), help="Output WebP path")
    arguments = parser.parse_args()
    written = capture(arguments.demo_host, Path(arguments.output))
    print(f"written {written} ({written.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
