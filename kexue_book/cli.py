from __future__ import annotations

from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path

from .crawl import crawl_posts
from .index import (
    group_by_topic,
    load_posts_from_json,
    print_topic_stats,
    write_posts_json,
    write_topic_index,
)
from .merge import merge_pdfs
from .render import render_posts_to_pdfs
from .taxonomy import (
    DEFAULT_TOPIC_IDS,
    TOPICS,
    resolve_topic_ids,
    topic_name,
)
from .types import Post


def _split_keywords(values: list[str] | None) -> list[str]:
    if not values:
        return []

    keywords: list[str] = []
    for value in values:
        keywords.extend(
            keyword.strip() for keyword in value.split(",") if keyword.strip()
        )
    return keywords


def _title_contains(title: str, keyword: str, case_sensitive: bool) -> bool:
    if case_sensitive:
        return keyword in title
    return keyword.casefold() in title.casefold()


def _filter_posts_by_title(
    posts: list[Post],
    include_keywords: list[str],
    exclude_keywords: list[str],
    include_match: str,
    case_sensitive: bool,
) -> list[Post]:
    filtered: list[Post] = []

    for post in posts:
        if include_keywords:
            matches = [
                _title_contains(post.title, keyword, case_sensitive)
                for keyword in include_keywords
            ]
            if include_match == "all":
                include_ok = all(matches)
            else:
                include_ok = any(matches)
        else:
            include_ok = True

        exclude_hit = any(
            _title_contains(post.title, keyword, case_sensitive)
            for keyword in exclude_keywords
        )

        if include_ok and not exclude_hit:
            filtered.append(post)

    return filtered


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description="Build a PDF book from Scientific Spaces posts, organized by topic."
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Start date YYYY-MM-DD (inclusive); required unless --list-topics",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="End date YYYY-MM-DD (inclusive); required unless --list-topics",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="output",
        help="Output directory (default: output)",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="BigData",
        help="Book name prefix (default: BigData)",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Debug: only process first N posts"
    )
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=4000,
        help="Extra wait time for MathJax rendering in milliseconds (default: 4000)",
    )

    parser.add_argument(
        "--order",
        choices=("asc", "desc"),
        default="asc",
        help="Sort posts by date: asc or desc (default: asc)",
    )
    parser.add_argument(
        "--cover",
        action="store_true",
        help="Add a cover page titled '苏剑林选集' at the beginning",
    )
    parser.add_argument(
        "--no-page-numbers",
        dest="page_numbers",
        action="store_false",
        help="Disable printing page numbers on each page",
    )
    parser.set_defaults(page_numbers=True)
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel render workers (default: 1)",
    )
    parser.add_argument(
        "--title-keyword",
        action="append",
        default=None,
        metavar="TEXT",
        help="Only keep posts whose title contains this keyword; repeat or comma-separate for multiple keywords",
    )
    parser.add_argument(
        "--title-match",
        choices=("any", "all"),
        default="any",
        help="How --title-keyword values are matched: any or all (default: any)",
    )
    parser.add_argument(
        "--exclude-title-keyword",
        action="append",
        default=None,
        metavar="TEXT",
        help="Exclude posts whose title contains this keyword; repeat or comma-separate for multiple keywords",
    )
    parser.add_argument(
        "--title-case-sensitive",
        action="store_true",
        help="Make title keyword matching case-sensitive",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse existing valid chapter PDFs and render only missing/invalid ones",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry only posts marked as failed in the previous manifest.json",
    )
    parser.add_argument(
        "--source-category",
        action="append",
        default=None,
        metavar="SLUG",
        help=(
            "Crawl only these native site categories (repeatable), e.g. Big-Data / Mathematics / Everything. "
            "Default: Big-Data, Mathematics, Everything"
        ),
    )
    parser.add_argument(
        "--topic",
        action="append",
        default=None,
        metavar="ID",
        help=(
            "Only keep posts classified into these topics (repeatable); "
            "run --list-topics to see all ids. Default: the 9 tech/math topics"
        ),
    )
    parser.add_argument(
        "--all-topics",
        action="store_true",
        help="Disable topic filtering and keep all 18 topics",
    )
    parser.add_argument(
        "--list-topics",
        action="store_true",
        help="Print the topic taxonomy (id, name, default-enabled) and exit",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Only crawl metadata, classify, and write index.md/posts.json (no rendering)",
    )
    parser.add_argument(
        "--per-category",
        action="store_true",
        help="Build one separate PDF book per topic instead of a single merged book",
    )
    parser.add_argument(
        "--from-json",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "Load previously crawled metadata (posts_all.json) instead of crawling; "
            "topics are re-classified with current rules"
        ),
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.list_topics:
        print(f"{'ID':<14s} {'名称':<14s} 默认启用")
        for topic in TOPICS:
            flag = "是" if topic.enabled_by_default else "-"
            print(f"{topic.topic_id:<14s} {topic.name:<14s} {flag}")
        print(
            "\n默认启用的主题可通过 --topic ID 覆盖；--all-topics 启用全部。"
        )
        return

    if not args.start or not args.end:
        raise SystemExit("[error] 需要同时提供 --start 与 --end（或使用 --list-topics）")

    start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end, "%Y-%m-%d").date()

    selected_topics = resolve_topic_ids(args.topic, all_topics=args.all_topics)
    print(
        f"[topic] 启用主题 {len(selected_topics)} 个: "
        + ", ".join(topic_name(t) for t in selected_topics)
    )

    if args.from_json:
        from pathlib import Path as _Path

        posts = load_posts_from_json(_Path(args.from_json))
        posts = [post for post in posts if start_date <= post.date <= end_date]
        # 用当前规则重新归类
        from .taxonomy import classify_title

        posts = [
            Post(
                title=post.title,
                url=post.url,
                date=post.date,
                categories=post.categories,
                topic=classify_title(post.title, post.primary_category),
            )
            for post in posts
        ]
        print(
            f"[load] 从 {args.from_json} 读取并重新归类: {len(posts)} 篇 "
            f"(区间 {start_date} ~ {end_date})"
        )
    else:
        print(f"[crawl] 区间: {start_date} ~ {end_date}")
        posts = crawl_posts(start_date, end_date, categories=args.source_category)
    print(f"[crawl] 命中文章数: {len(posts)}")

    # 全量元数据先落盘（含未入选主题的文章，便于调规则复盘）
    write_posts_json(posts, Path(args.out_dir) / "posts_all.json")

    # 主题过滤（默认只保留 9 个技术/数学主题）
    before_topic_filter = len(posts)
    posts = [post for post in posts if post.topic in selected_topics]
    print(
        f"[filter] 主题过滤: {before_topic_filter} -> {len(posts)} 篇 "
        f"(启用 {len(selected_topics)} 个主题)"
    )

    include_keywords = _split_keywords(args.title_keyword)
    exclude_keywords = _split_keywords(args.exclude_title_keyword)
    if include_keywords or exclude_keywords:
        before_filter = len(posts)
        posts = _filter_posts_by_title(
            posts,
            include_keywords=include_keywords,
            exclude_keywords=exclude_keywords,
            include_match=args.title_match,
            case_sensitive=args.title_case_sensitive,
        )
        print(
            f"[filter] 标题关键词过滤: {before_filter} -> {len(posts)} 篇"
        )
        if include_keywords:
            print(f"[filter] 包含关键词({args.title_match}): {', '.join(include_keywords)}")
        if exclude_keywords:
            print(f"[filter] 排除关键词: {', '.join(exclude_keywords)}")

    if args.order == "desc":
        posts = list(reversed(posts))

    if args.limit:
        before_limit = len(posts)
        posts = posts[: args.limit]
        print(f"[filter] limit: {before_limit} -> {len(posts)} 篇")

    if not posts:
        raise SystemExit("[error] 指定区间没有命中文章，已退出。")

    out_dir = Path(args.out_dir)

    # 元数据模式：只输出主题索引与统计，不做渲染
    if args.metadata_only:
        write_topic_index(posts, out_dir, topic_order=selected_topics)
        return

    print_topic_stats(group_by_topic(posts))

    if args.per_category:
        _build_per_category_books(posts, args)
        return

    _build_single_book(posts, args)


def _build_single_book(posts: list[Post], args) -> None:
    out_dir = Path(args.out_dir)
    chapters_dir = out_dir / "chapters"
    manifest_path = out_dir / "manifest.json"

    if args.retry_failed and not manifest_path.exists():
        raise SystemExit(f"[error] --retry-failed 找不到 manifest: {manifest_path}")

    render_output = render_posts_to_pdfs(
        posts,
        chapters_dir,
        delay_ms=args.delay_ms,
        workers=args.workers,
        manifest_path=manifest_path,
        resume=args.resume,
        retry_failed=args.retry_failed,
    )

    success_records = [
        record for record in render_output.records if record.status == "success"
    ]
    failed_records = [
        record for record in render_output.records if record.status != "success"
    ]
    print(
        f"[check] 渲染完整性: 成功 {len(success_records)} 篇，"
        f"失败 {len(failed_records)} 篇；manifest: {manifest_path}"
    )
    if failed_records:
        print("[check] 缺失 URL:")
        for record in failed_records:
            reason = record.failure_reason or "unknown"
            print(f"  - #{record.index:03d} {record.post.url} ({reason})")
        print("[check] 将只合并成功生成且可读取的章节 PDF。")

    if not render_output.rendered_posts:
        raise SystemExit("[error] 没有成功渲染任何文章，已退出。")
    if len(render_output.pdf_paths) != len(render_output.rendered_posts):
        raise SystemExit("[error] 渲染结果数量不一致，请重试。")

    book_path = out_dir / f"{args.name}-{args.start}-{args.end}.pdf"
    merge_pdfs(
        render_output.pdf_paths,
        render_output.rendered_posts,
        book_path,
        add_bookmarks=True,
        add_cover=args.cover,
        add_page_numbers=args.page_numbers,
        cover_title="苏剑林选集",
        group_by_topics=True,
    )

    print(f"[done] 书籍已生成，可以拷到 iPad 上阅读： {book_path}")


def _build_per_category_books(posts: list[Post], args) -> None:
    """每个主题一本独立 PDF，输出到 out_dir/<topic-id>/ 子目录。"""
    out_dir = Path(args.out_dir)
    grouped = group_by_topic(posts)
    # 保持 --order desc 时的组内顺序；主题顺序按 taxonomy 定义
    from .taxonomy import TOPIC_BY_ID

    topic_order = sorted(
        grouped, key=lambda t: list(TOPIC_BY_ID).index(t) if t in TOPIC_BY_ID else 999
    )

    books: list[Path] = []
    for topic_id in topic_order:
        topic_posts = grouped[topic_id]
        topic_dir = out_dir / topic_id
        print(
            f"\n[book] ===== {topic_name(topic_id)} ({len(topic_posts)} 篇) ====="
        )

        render_output = render_posts_to_pdfs(
            topic_posts,
            topic_dir / "chapters",
            delay_ms=args.delay_ms,
            workers=args.workers,
            manifest_path=topic_dir / "manifest.json",
            resume=args.resume,
            retry_failed=args.retry_failed,
        )
        if not render_output.rendered_posts:
            print(f"[book] {topic_name(topic_id)} 没有成功渲染的文章，跳过。")
            continue

        book_path = topic_dir / f"{topic_id}-{args.start}-{args.end}.pdf"
        merge_pdfs(
            render_output.pdf_paths,
            render_output.rendered_posts,
            book_path,
            add_bookmarks=True,
            add_cover=args.cover,
            add_page_numbers=args.page_numbers,
            cover_title=f"苏剑林选集 · {topic_name(topic_id)}",
            group_by_topics=False,
        )
        books.append(book_path)
        print(f"[done] 已生成: {book_path}")

    print(f"\n[done] 共生成 {len(books)} 本分册：")
    for path in books:
        print(f"  - {path}")


if __name__ == "__main__":
    main()
