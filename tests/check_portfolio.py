"""Checks that index.html has the content and constraints the portfolio requires.

Run from the site folder: python -I tests/check_portfolio.py
Prints OK and exits 0 when every check passes; otherwise lists failures and exits 1.
"""

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "index.html"
GITHUB_PROFILE = "https://github.com/ShaneIsDelightful"
INTRO = "Software developer and technical trainer. I build things."
FONT_STACK = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
BRAND_VARIABLES = {
    "--learn-pink": "#e60073",
    "--electric-blue": "#00b4d8",
    "--deep-charcoal": "#1a1a1d",
    "--crisp-white": "#fefefe",
    "--gunmetal": "#3d3d3d",
    "--learn-pink-dark": "#99004d",
    "--electric-blue-dark": "#007a92",
    "--crisp-white-dark": "#0d0d0e",
    "--deep-charcoal-dark": "#fefefe",
}
EXPECTED_PROJECTS = [
    ("Demo", "HTML", "Sample repository used for class demo."),
    ("BookSearch", "JavaScript", "Full-stack JavaScript book search app with a separate client and server."),
    ("Project2", "Python", "Python Flask web app backed by MongoDB, deployed to Heroku."),
    ("WordGuess", "JavaScript", "Guess the letters in a randomly chosen word."),
    ("Zmpp.Core", "C#", "Zmpp.Core is a fork of the Z-Machine Preservation Project (ZMPP) ported to .NET"),
    ("microservice", "Java", "Demo microservice"),
    ("Financials", "C#", "CRUD/REST Demo for ASP.NET Core"),
    ("DigitalPets", "JavaScript", "Take care of digital pets and battle them against each other."),
    ("RockPaperScissors", "JavaScript", "A simple game of rock, paper, scissors."),
    ("turboOctoBroccoli", "JavaScript", "Demo repository"),
]


class Region:
    """Text, link targets, link elements, and classed elements found inside one element."""

    def __init__(self):
        self.text = ""
        self.links = []
        self.anchors = []
        self.classes = {}

    def first_text(self, css_class):
        """Returns the normalized text of the first element inside this one with `css_class`, or ""."""
        regions = self.classes.get(css_class)
        return normalized(regions[0].text) if regions else ""


class PageParser(HTMLParser):
    """Collects the text and links of the header, the footer, and each element by class."""

    def __init__(self):
        super().__init__()
        self.regions = {}
        self.class_regions = {}
        self.open = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        regions = []
        if tag in ("header", "footer"):
            self.regions[tag] = Region()
            regions.append(self.regions[tag])
        for css_class in (attributes.get("class") or "").split():
            region = Region()
            self.class_regions.setdefault(css_class, []).append(region)
            for enclosing in self.active_regions():
                enclosing.classes.setdefault(css_class, []).append(region)
            regions.append(region)
        if tag == "a":
            anchor = Region()
            for region in self.active_regions():
                region.anchors.append(anchor)
                if attributes.get("href"):
                    region.links.append(attributes["href"])
            regions.append(anchor)
        self.open.append((tag, regions))

    def handle_endtag(self, tag):
        for index in range(len(self.open) - 1, -1, -1):
            if self.open[index][0] == tag:
                del self.open[index:]
                return

    def handle_data(self, data):
        # Text nodes are kept apart so words in neighboring elements never run together.
        for region in self.active_regions():
            region.text += data + " "

    def active_regions(self):
        for _, regions in self.open:
            yield from regions


class Page:
    """The page source and its parsed structure, read once and shared by every check."""

    def __init__(self, path):
        self.source = path.read_text(encoding="utf-8")
        self.parsed = PageParser()
        self.parsed.feed(self.source)

    def css_rule(self, selector):
        """Returns the declarations of the first CSS rule whose selector is exactly `selector`."""
        match = re.search(r"(?:^|[}\s])" + re.escape(selector) + r"\s*\{([^}]*)\}", self.source)
        return match.group(1) if match else None


def normalized(text):
    return " ".join(text.split())


def check_no_script(page):
    if "<script" in page.source.lower():
        return ["page contains a <script> tag"]
    return []


def check_no_external_assets(page):
    source = page.source.lower()
    failures = []
    if re.search(r'<link[^>]*rel="stylesheet"', source):
        failures.append("page links an external stylesheet")
    if "<img" in source:
        failures.append("page contains an <img>")
    if "@import" in source or "url(" in source:
        failures.append("page CSS loads an external resource")
    return failures


def check_brand_variables(page):
    return [
        f"missing {name}: {value}"
        for name, value in BRAND_VARIABLES.items()
        if not re.search(re.escape(name) + r"\s*:\s*" + re.escape(value) + r"\s*;", page.source, re.IGNORECASE)
    ]


def check_card_background_uses_brand_variables(page):
    expected = ["--bg-card: var(--crisp-white);", "--bg-card: var(--deep-charcoal);"]
    return [f"missing {declaration}" for declaration in expected if declaration not in page.source]


def check_dark_mode(page):
    if not re.search(r"@media\s*\(\s*prefers-color-scheme\s*:\s*dark\s*\)", page.source):
        return ["missing @media (prefers-color-scheme: dark)"]
    return []


def check_font_stack(page):
    if FONT_STACK not in page.source:
        return ["missing the delightfultts.com font stack"]
    return []


def check_viewport(page):
    if '<meta name="viewport" content="width=device-width, initial-scale=1">' not in page.source:
        return ["missing viewport meta tag"]
    return []


def check_header(page):
    header = page.parsed.regions.get("header")
    if header is None:
        return ["missing <header>"]
    text = normalized(header.text)
    failures = [f"header text missing {expected!r}" for expected in ("Shane", "ShaneIsDelightful", INTRO) if expected not in text]
    if GITHUB_PROFILE not in header.links:
        failures.append("header missing GitHub profile link")
    return failures


def check_footer(page):
    footer = page.parsed.regions.get("footer")
    if footer is None:
        return ["missing <footer>"]
    return [
        f"footer missing link {link}"
        for link in (GITHUB_PROFILE, "https://www.delightfultts.com/")
        if link not in footer.links
    ]


def project_cards(page):
    """Returns (name, href, language, description) for each .project card in page order."""
    return [
        (
            normalized(project.anchors[0].text) if project.anchors else "",
            project.links[0] if project.links else "",
            project.first_text("language"),
            project.first_text("description"),
        )
        for project in page.parsed.class_regions.get("project", [])
    ]


def check_projects(page):
    cards = project_cards(page)
    if len(cards) != len(EXPECTED_PROJECTS):
        return [f"found {len(cards)} of {len(EXPECTED_PROJECTS)} project cards"]
    failures = []
    for position, (card, (repo, language, description)) in enumerate(zip(cards, EXPECTED_PROJECTS), start=1):
        expected = (repo, f"{GITHUB_PROFILE}/{repo}", language, description)
        if card != expected:
            failures.append(f"card {position} is {card}, expected {expected}")
    return failures


def check_no_stale_numbers(page):
    return [
        f"project card contains a star count or date: {normalized(project.text)!r}"
        for project in page.parsed.class_regions.get("project", [])
        if re.search(r"\b(stars?|updated)\b|\b20\d\d\b", project.text, re.IGNORECASE)
    ]


def check_header_colors(page):
    # The header is Deep Charcoal in both modes, set apart from the page by a Learn Pink bottom border.
    failures = []
    if re.findall(r"--bg-header\s*:\s*([^;]+);", page.source) != ["var(--deep-charcoal)"]:
        failures.append("--bg-header must be set once, to var(--deep-charcoal)")
    declarations = page.css_rule("header") or ""
    for expected in ("background: var(--bg-header);", "border-bottom: 4px solid var(--learn-pink);"):
        if expected not in declarations:
            failures.append(f"header rule missing {expected}")
    return failures


def check_header_handle_fully_opaque(page):
    # White on Learn Pink is 4.51:1, so any transparency drops the handle below WCAG AA.
    declarations = page.css_rule("header .handle")
    if declarations is None:
        return ["missing CSS rule for header .handle"]
    if "opacity" in declarations:
        return ["header .handle sets opacity, which drops its contrast below 4.5:1"]
    return []


def check_focus_outline_uses_link_color(page):
    # The link color meets 3:1 against cards and page in both modes; the brand accent does not in light mode.
    declarations = page.css_rule("a:focus-visible")
    if declarations is None or "outline: 3px solid var(--link-color)" not in declarations:
        return ["a:focus-visible outline must use var(--link-color)"]
    return []


def check_card_lift_on_keyboard_focus(page):
    if not re.search(r"\.project:hover,\s*\.project:focus-within\s*\{", page.source):
        return ["card lift must apply to .project:focus-within as well as :hover"]
    return []


def check_reduced_motion(page):
    match = re.search(r"@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)\s*\{(.*?)\}\s*\}", page.source, re.DOTALL)
    if match is None or "transition: none" not in match.group(1) or "transform: none" not in match.group(1):
        return ["missing prefers-reduced-motion rule turning off the card transition and lift"]
    return []


def check_ascii_only(page):
    return [
        f"page contains a non-ASCII character on line {line_number}"
        for line_number, line in enumerate(page.source.splitlines(), start=1)
        if not line.isascii()
    ]


CHECKS = [
    check_no_script,
    check_no_external_assets,
    check_brand_variables,
    check_card_background_uses_brand_variables,
    check_dark_mode,
    check_font_stack,
    check_viewport,
    check_header,
    check_footer,
    check_projects,
    check_no_stale_numbers,
    check_header_colors,
    check_header_handle_fully_opaque,
    check_focus_outline_uses_link_color,
    check_card_lift_on_keyboard_focus,
    check_reduced_motion,
    check_ascii_only,
]


def failures(path=None):
    """Runs every check against the page and returns the failure messages."""
    page = Page(path or PAGE)
    return [f"{check.__name__}: {failure}" for check in CHECKS for failure in check(page)]


def main():
    if not PAGE.exists():
        print(f"FAIL: {PAGE} does not exist")
        return 1
    found = failures()
    if found:
        print("\n".join(f"FAIL {failure}" for failure in found))
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
