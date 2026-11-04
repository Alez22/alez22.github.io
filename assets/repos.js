/**
 * @file repos.js
 * @brief Loads the public, non-fork repositories of GITHUB_USER and renders them
 *        into the element with id "repo-list".
 *
 * Constraints:
 *  - Unauthenticated GitHub API: 60 requests/hour per visitor IP.
 *  - Only the first 100 repositories are fetched (one page, no pagination).
 *  - Repo data is external input: it is inserted with textContent only, never innerHTML.
 */

const GITHUB_USER = "alez22";
const API_URL = "https://api.github.com/users/" + GITHUB_USER + "/repos?per_page=100&sort=pushed";
const PROFILE_URL = "https://github.com/" + GITHUB_USER;

/**
 * @brief Creates an element with an optional class and text content.
 * @param tag        HTML tag name.
 * @param class_name CSS class, or empty string for none.
 * @param text       Plain text (escaped automatically by textContent).
 * @return The new element.
 */
function createElement(tag, class_name, text) {
  const element = document.createElement(tag);
  if (class_name) element.className = class_name;
  if (text) element.textContent = text;
  return element;
}

/**
 * @brief Builds one list item for a repository.
 * @param repo A repository object from the GitHub API (untrusted).
 * @return The <li> element.
 */
function createRepoItem(repo) {
  const item = document.createElement("li");

  const link = createElement("a", "item-title", repo.name);
  link.href = repo.html_url;
  item.appendChild(link);

  if (repo.description) {
    item.appendChild(createElement("span", "desc", repo.description));
  }

  // pushed_at is ISO 8601; the first 10 chars are the date (YYYY-MM-DD).
  const language = repo.language || "n/a";
  const updated = String(repo.pushed_at || "").slice(0, 10);
  item.appendChild(createElement("span", "meta", language + " · updated " + updated));
  return item;
}

/**
 * @brief Replaces the list content with a message and a link to the profile.
 * @param container The list element.
 * @param message   Short explanation shown to the visitor.
 */
function showFallback(container, message) {
  container.replaceChildren();
  const item = createElement("li", "desc", message + " ");
  const link = createElement("a", "", "See all repositories on GitHub");
  link.href = PROFILE_URL;
  item.appendChild(link);
  container.appendChild(item);
}

/**
 * @brief Fetches the repositories and renders them, or shows a fallback on failure.
 */
async function loadRepos() {
  const container = document.getElementById("repo-list");
  if (!container) return;

  let raw_repos;
  try {
    const response = await fetch(API_URL);
    // 403/429 usually means the hourly rate limit was hit.
    if (!response.ok) {
      showFallback(container, "Could not load the repository list (HTTP " + response.status + ").");
      return;
    }
    raw_repos = await response.json();
  } catch (error) {
    showFallback(container, "Could not reach GitHub.");
    return;
  }

  if (!Array.isArray(raw_repos)) {
    showFallback(container, "Unexpected answer from GitHub.");
    return;
  }

  const own_repos = raw_repos.filter((repo) => !repo.fork);
  if (own_repos.length === 0) {
    showFallback(container, "No public repositories yet.");
    return;
  }

  container.replaceChildren(...own_repos.map(createRepoItem));
}

loadRepos();
