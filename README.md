# alez22.github.io

Personal site: about, projects (live from the GitHub API) and notes.
Plain HTML/CSS, Markdown content, one small Python build script.

## Layout

| Path | Purpose |
|------|---------|
| `content/home.md` | Intro line of the home page (`/`); the notes list is added below it |
| `content/about.md` | About page (`/about.html`) |
| `content/projects.md` | Projects page; the repo list is filled by `assets/repos.js` |
| `content/posts/YYYY-MM-DD-slug.md` | One note per file, published at `/posts/slug.html` |
| `templates/page.html` | Shared layout (nav, footer) |
| `assets/` | CSS, JS, self-hosted fonts (IBM Plex, SIL OFL, see `assets/fonts/OFL.txt`) |
| `build.py` | Converts `content/` into `_site/` |
| `.github/workflows/pages.yml` | Builds and deploys on every push to `main` |

## Writing a note

Create `content/posts/2026-11-04-my-topic.md`:

```
title: My topic
date: 2026-11-04
---
Markdown text here.
```

The build stops with an error if the header, date or file name is malformed.

## Local preview

```
pip install -r requirements.txt
python3 build.py
python3 -m http.server -d _site 8000
```

Then open http://localhost:8000.

## Known limits

- The projects list uses the unauthenticated GitHub API: 60 requests/hour per visitor IP.
  When exceeded, the page shows a link to the GitHub profile instead.
- Only the first 100 repositories are listed.
