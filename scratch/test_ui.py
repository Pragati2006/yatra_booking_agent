import time
from playwright.sync_api import sync_playwright

def inspect_ui():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto("http://localhost:8503")
        page.wait_for_selector(".brand-title", timeout=15000)
        time.sleep(2)
        
        # Take screenshot of hero section
        page.screenshot(path="hero_screenshot.png")
        
        # Get bounding box of .brand-title and header
        brand_title_box = page.locator(".brand-title").bounding_box()
        header_box = page.locator("header[data-testid='stHeader']").bounding_box() if page.locator("header[data-testid='stHeader']").count() > 0 else None
        
        print("Brand title box:", brand_title_box)
        print("Header box:", header_box)
        
        # Get computed styles
        styles = page.evaluate("""() => {
            const el = document.querySelector('.brand-title');
            const comp = window.getComputedStyle(el);
            const blockComp = window.getComputedStyle(document.querySelector('.block-container'));
            return {
                titleLineHeight: comp.lineHeight,
                titleFontSize: comp.fontSize,
                titlePaddingTop: comp.paddingTop,
                titleMarginTop: comp.marginTop,
                blockPaddingTop: blockComp.paddingTop,
                blockOverflow: blockComp.overflow
            };
        }""")
        print("Computed styles:", styles)
        browser.close()

if __name__ == "__main__":
    inspect_ui()
