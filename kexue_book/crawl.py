from __future__ import annotations

import time
from datetime import date, datetime
from typing import Iterable, List
from urllib.parse import urljoin
import re

import requests
from bs4 import BeautifulSoup

from .taxonomy import DEFAULT_SOURCE_CATEGORIES, NATIVE_CATEGORIES, classify_title
from .types import Post

SITE_BASE = "https://spaces.ac.cn"
BASE_CATEGORY_URL = f"{SITE_BASE}/category/Big-Data"
DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")
ARCHIVE_ID_PATTERN = re.compile(r"/(\d+)$")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 站点有基于 Cookie 的反爬质询：首次请求返回 403 并 Set-Cookie，
# 带 Cookie 重试即可通过。最多重试这么多次。
CHALLENGE_RETRIES = 3


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session


def fetch_html(session: requests.Session, url: str, timeout: int = 20) -> str:
    """GET 一个页面；遇到 Cookie 质询（403）时自动带 Cookie 重试。"""
    last_error: requests.RequestException | None = None
    for attempt in range(1, CHALLENGE_RETRIES + 1):
        try:
            response = session.get(url, timeout=timeout)
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(1.0 * attempt)
            continue

        if response.status_code == 200:
            return response.text
        if response.status_code == 403:
            # 质询：响应里已 Set-Cookie，立即用同一 Session 重试
            time.sleep(0.5 * attempt)
            continue

        response.raise_for_status()

    raise RuntimeError(
        f"页面在 {CHALLENGE_RETRIES} 次尝试后仍无法访问: {url} "
        f"(last error: {last_error})"
    )


def _parse_post(post_element: BeautifulSoup, native_slug: str) -> Post:
    title_el = post_element.select_one("h2 a")
    if not title_el or not title_el.get("href"):
        raise ValueError("Post node is missing title link")

    title = title_el.get_text(strip=True)
    url = urljoin(f"{SITE_BASE}/category/{native_slug}", title_el["href"])

    meta_text = post_element.select_one("span.submitted")
    if not meta_text:
        raise ValueError(f"Missing metadata for post: {title}")

    match = DATE_PATTERN.search(meta_text.get_text(" "))
    if not match:
        raise ValueError(f"Missing date for post: {title}")

    publish_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()

    return Post(
        title=title,
        url=url,
        date=publish_date,
        categories=(native_slug,),
        topic=classify_title(title, native_slug),
    )


def _find_next_page(soup: BeautifulSoup, current_url: str) -> str | None:
    next_link = soup.find("a", string="»")
    if not next_link or not next_link.get("href"):
        return None
    return urljoin(current_url, next_link["href"])


def _crawl_single_category(
    session: requests.Session,
    native_slug: str,
    start: date,
    end: date,
    request_interval: float,
) -> List[Post]:
    """抓取一个原生分类下的所有文章（时间区间过滤交给调用方）。"""
    posts: List[Post] = []
    seen_pages: set[str] = set()

    page_url: str | None = f"{SITE_BASE}/category/{native_slug}"
    while page_url and page_url not in seen_pages:
        html = fetch_html(session, page_url)
        soup = BeautifulSoup(html, "lxml")
        seen_pages.add(page_url)

        for post_element in soup.select("div.Post"):
            try:
                post = _parse_post(post_element, native_slug)
            except ValueError:
                continue

            if start <= post.date <= end:
                posts.append(post)

        page_url = _find_next_page(soup, page_url)
        time.sleep(request_interval)

    return posts


def crawl_posts(
    start: date,
    end: date,
    categories: Iterable[str] | None = None,
    request_interval: float = 0.35,
    classify: bool = True,
) -> List[Post]:
    """抓取若干原生分类，去重合并后按日期返回。

    一篇文章可能同时属于多个原生分类；去重时合并 categories 列表，
    主分类按 taxonomy.CRAWL_PRIORITY 决定，主题按主分类重新归类。
    """
    slugs = list(categories) if categories else list(DEFAULT_SOURCE_CATEGORIES)
    for slug in slugs:
        if slug not in NATIVE_CATEGORIES:
            raise SystemExit(
                f"[error] 未知原生分类: {slug}。可用: "
                + ", ".join(f"{s}({c.name})" for s, c in NATIVE_CATEGORIES.items())
            )

    session = make_session()
    by_url: dict[str, Post] = {}

    for slug in slugs:
        print(f"[crawl] 原生分类: {slug} ({NATIVE_CATEGORIES[slug].name})")
        posts = _crawl_single_category(session, slug, start, end, request_interval)
        print(f"[crawl]   采集到 {len(posts)} 篇")

        for post in posts:
            existing = by_url.get(post.url)
            if existing is None:
                by_url[post.url] = post
            else:
                merged = sorted(
                    set(existing.categories) | set(post.categories),
                    key=lambda s: (
                        list(NATIVE_CATEGORIES).index(s)
                        if s in NATIVE_CATEGORIES
                        else 99
                    ),
                )
                by_url[post.url] = Post(
                    title=existing.title,
                    url=existing.url,
                    date=existing.date,
                    categories=tuple(merged),
                    topic=existing.topic,
                )

    posts = list(by_url.values())

    if classify:
        for post in posts:
            by_url[post.url] = Post(
                title=post.title,
                url=post.url,
                date=post.date,
                categories=post.categories,
                topic=classify_title(post.title, post.primary_category),
            )
        posts = list(by_url.values())

    def _sort_key(p: Post) -> tuple[date, int]:
        # Use archive id as tie-breaker so posts on the same date follow publish order.
        match = ARCHIVE_ID_PATTERN.search(p.url)
        archive_id = int(match.group(1)) if match else 0
        return (p.date, archive_id)

    posts.sort(key=_sort_key)
    return posts


def iter_posts(start: date, end: date) -> Iterable[Post]:
    """Yield posts within the given date range in chronological order."""

    for post in crawl_posts(start, end):
        yield post
