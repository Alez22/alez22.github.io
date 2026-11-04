#!/usr/bin/env python3
"""
@file build.py
@brief Converts the Markdown files in content/ into a static site in _site/.

Input layout:
  content/home.md               -> _site/index.html (intro line + list of all posts)
  content/about.md              -> _site/about.html
  content/projects.md           -> _site/projects.html
  content/posts/YYYY-MM-DD-slug.md -> _site/posts/slug.html
  assets/                       -> _site/assets/ (copied as-is)

Each Markdown file starts with a small header, closed by a line with "---":
  title: Some title
  date: 2026-11-04      (required for posts only)
  ---
  Markdown body...

Any malformed input stops the build with an error, so a broken page is never published.
Dependency: the "markdown" package (pip install markdown).
"""

import datetime
import html
import re
import shutil
import sys
from pathlib import Path

import markdown

ROOT_DIR = Path(__file__).parent
CONTENT_DIR = ROOT_DIR / "content"
POSTS_DIR = CONTENT_DIR / "posts"
ASSETS_DIR = ROOT_DIR / "assets"
TEMPLATE_FILE = ROOT_DIR / "templates" / "page.html"
OUTPUT_DIR = ROOT_DIR / "_site"

SITE_NAME = "alez22"
MARKDOWN_EXTENSIONS = ["fenced_code", "tables"]
# Post file names must look like 2026-11-04-my-post.md; the slug becomes the URL.
POST_FILENAME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}-([a-z0-9-]+)\.md$")
HEADER_SEPARATOR = "---"


def fail(message):
    """
    @brief Prints an error and stops the build with a non-zero exit code.
    @param message Explanation of what is wrong and where.
    """
    print("BUILD ERROR: " + message, file=sys.stderr)
    sys.exit(1)


def read_source(path):
    """
    @brief Splits a Markdown file into its header fields and its body.
    @param path Path of the Markdown file.
    @return (header dict, markdown body string).
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if HEADER_SEPARATOR not in lines:
        fail(f"{path}: missing '{HEADER_SEPARATOR}' line closing the header")

    separator_index = lines.index(HEADER_SEPARATOR)
    header = {}
    for line in lines[:separator_index]:
        if not line.strip():
            continue
        if ":" not in line:
            fail(f"{path}: header line without ':' -> {line!r}")
        key, value = line.split(":", 1)
        header[key.strip()] = value.strip()

    if not header.get("title"):
        fail(f"{path}: header has no 'title'")

    body = "\n".join(lines[separator_index + 1:])
    return header, body


def render_page(template, page_title, content_html, active_nav, scripts=""):
    """
    @brief Fills the page template with plain string replacement.
    @param template     Template text with {{placeholders}}.
    @param page_title   Unescaped title; escaped here.
    @param content_html Already-rendered HTML for the main area.
    @param active_nav   One of "about", "projects", "blog", or "" for none.
    @param scripts      Extra <script> tags to put before </body>.
    @return The complete HTML document.
    """
    full_title = SITE_NAME if page_title == SITE_NAME else f"{page_title} · {SITE_NAME}"
    page = template.replace("{{title}}", html.escape(full_title))
    for nav_name in ("about", "projects", "blog"):
        marker = ' class="on"' if nav_name == active_nav else ""
        page = page.replace("{{nav_" + nav_name + "}}", marker)
    page = page.replace("{{scripts}}", scripts)
    # Content goes last so that "{{...}}" written inside a post is never replaced.
    return page.replace("{{content}}", content_html)


def markdown_to_html(markdown_text):
    """
    @brief Converts Markdown to HTML with the site's extensions.
    @note  Raw HTML in the Markdown is kept as-is: content is written by the site owner only.
    """
    return markdown.markdown(markdown_text, extensions=MARKDOWN_EXTENSIONS)


def write_output(relative_path, text):
    """
    @brief Writes a file under the output directory, creating folders as needed.
    """
    target = OUTPUT_DIR / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def load_post(path):
    """
    @brief Reads and validates one post.
    @param path Path of a file in content/posts/.
    @return dict with title, date (datetime.date), slug, body_html.
    """
    filename_match = POST_FILENAME_PATTERN.match(path.name)
    if not filename_match:
        fail(f"{path}: file name must look like YYYY-MM-DD-my-post.md (lowercase, digits, dashes)")

    header, body = read_source(path)
    raw_date = header.get("date", "")
    try:
        post_date = datetime.date.fromisoformat(raw_date)
    except ValueError:
        fail(f"{path}: 'date' must be YYYY-MM-DD, got {raw_date!r}")

    return {
        "title": header["title"],
        "date": post_date,
        "slug": filename_match.group(1),
        "body_html": markdown_to_html(body),
    }


def build_posts(template):
    """
    @brief Renders every post page and the home page (intro from home.md + post list).
    """
    posts = [load_post(path) for path in sorted(POSTS_DIR.glob("*.md"))]
    posts.sort(key=lambda post: post["date"], reverse=True)

    slugs = [post["slug"] for post in posts]
    duplicate_slugs = {slug for slug in slugs if slugs.count(slug) > 1}
    if duplicate_slugs:
        fail(f"duplicate post slugs (two posts would get the same URL): {sorted(duplicate_slugs)}")

    index_items = []
    for post in posts:
        safe_title = html.escape(post["title"])
        iso_date = post["date"].isoformat()
        post_html = (
            f"<article>\n<h1>{safe_title}</h1>\n"
            f'<p class="meta"><time datetime="{iso_date}">{iso_date}</time></p>\n'
            f"{post['body_html']}\n</article>"
        )
        write_output(f"posts/{post['slug']}.html", render_page(template, post["title"], post_html, "blog"))
        index_items.append(
            f'<li><a class="item-title" href="/posts/{post["slug"]}.html">{safe_title}</a>'
            f'<span class="meta">{iso_date}</span></li>'
        )

    if index_items:
        list_html = '<ul class="item-list">\n' + "\n".join(index_items) + "\n</ul>"
    else:
        list_html = '<p class="desc">No notes yet.</p>'

    home_header, home_body = read_source(CONTENT_DIR / "home.md")
    home_html = (
        f'<div class="home-intro">{markdown_to_html(home_body)}</div>\n'
        f'<p class="section-label">Notes</p>\n{list_html}'
    )
    write_output("index.html", render_page(template, home_header["title"], home_html, "blog"))
    print(f"built {len(posts)} post(s)")


def build_static_page(template, source_name, output_name, active_nav, scripts=""):
    """
    @brief Renders one standalone page (about, projects) from content/.
    """
    header, body = read_source(CONTENT_DIR / source_name)
    page_html = render_page(template, header["title"], markdown_to_html(body), active_nav, scripts)
    write_output(output_name, page_html)


def main():
    """
    @brief Rebuilds _site/ from scratch so deleted posts never linger.
    """
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    shutil.copytree(ASSETS_DIR, OUTPUT_DIR / "assets")

    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    build_static_page(template, "about.md", "about.html", "about")
    build_static_page(template, "projects.md", "projects.html", "projects",
                      '<script src="/assets/repos.js" defer></script>')
    build_posts(template)

    # Tell GitHub Pages not to run Jekyll on the output.
    write_output(".nojekyll", "")
    print(f"site written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
