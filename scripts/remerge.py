"""用已渲染的章节 PDF 重新合并整书（不重新渲染）。

改完排序/书签/分类规则后想重建整本 PDF 时使用：

    python scripts/remerge.py output --name Kexue-Topics

需要 out_dir 下同时有 manifest.json（渲染记录）和 posts_all.json
（元数据，用于重新归类与排序）。主题、日期信息以当前 taxonomy
规则重新计算，章节 PDF 按 URL 关联复用。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kexue_book.index import load_posts_from_json  # noqa: E402
from kexue_book.merge import merge_pdfs  # noqa: E402
from kexue_book.taxonomy import (  # noqa: E402
    DEFAULT_TOPIC_IDS,
    classify_title,
    resolve_topic_ids,
)
from kexue_book.types import Post  # noqa: E402

ARCHIVE_ID_PATTERN = re.compile(r"/(\d+)$")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out_dir", type=Path, help="渲染输出目录（含 manifest.json 与 posts_all.json）")
    parser.add_argument("--name", type=str, default=None, help="输出 PDF 文件名前缀（默认沿用 manifest 元数据推断）")
    parser.add_argument("--start", type=str, default=None, help="起始日期过滤 YYYY-MM-DD（可选）")
    parser.add_argument("--end", type=str, default=None, help="结束日期过滤 YYYY-MM-DD（可选）")
    parser.add_argument("--topic", action="append", default=None, help="同 cli 的 --topic")
    parser.add_argument("--all-topics", action="store_true", help="保留全部主题")
    parser.add_argument("--cover", action="store_true", help="添加封面")
    parser.add_argument("--no-page-numbers", dest="page_numbers", action="store_false")
    parser.set_defaults(page_numbers=True)
    args = parser.parse_args()

    out_dir: Path = args.out_dir
    manifest_path = out_dir / "manifest.json"
    posts_all_path = out_dir / "posts_all.json"
    if not manifest_path.exists() or not posts_all_path.exists():
        raise SystemExit(f"[error] 需要 {manifest_path} 和 {posts_all_path} 同时存在")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = [e for e in manifest.get("entries", []) if e.get("status") == "success"]

    meta_by_url = {post.url: post for post in load_posts_from_json(posts_all_path)}

    selected = resolve_topic_ids(args.topic, all_topics=args.all_topics)
    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None

    pairs: list[tuple[Path, Post]] = []
    for entry in entries:
        post = meta_by_url.get(entry["url"])
        if post is None:
            print(f"[skip] manifest 中的文章不在 posts_all.json: {entry['url']}")
            continue
        if start and post.date < start:
            continue
        if end and post.date > end:
            continue
        # 以当前规则重新归类
        topic = classify_title(post.title, post.primary_category)
        if topic not in selected:
            continue
        pdf_path = Path(entry["pdf_path"])
        if not pdf_path.is_absolute():
            pdf_path = out_dir / pdf_path
        if not pdf_path.exists():
            print(f"[skip] 章节 PDF 缺失: {pdf_path}")
            continue
        pairs.append(
            (
                pdf_path,
                Post(
                    title=post.title,
                    url=post.url,
                    date=post.date,
                    categories=post.categories,
                    topic=topic,
                ),
            )
        )

    topic_rank = {t: i for i, t in enumerate(selected)}
    pairs.sort(
        key=lambda pair: (
            topic_rank.get(pair[1].topic, len(selected)),
            pair[1].date,
            int(ARCHIVE_ID_PATTERN.search(pair[1].url).group(1))
            if ARCHIVE_ID_PATTERN.search(pair[1].url)
            else 0,
        )
    )

    print(f"[remerge] 参与合并: {len(pairs)} 篇")
    name = args.name or "Kexue-Topics"
    dates = [pair[1].date for pair in pairs]
    book_path = out_dir / f"{name}-{min(dates).isoformat()}-{max(dates).isoformat()}.pdf"
    merge_pdfs(
        [p for p, _ in pairs],
        [post for _, post in pairs],
        book_path,
        add_bookmarks=True,
        add_cover=args.cover,
        add_page_numbers=args.page_numbers,
        cover_title="苏剑林选集",
        group_by_topics=True,
    )
    print(f"[done] 已重建整书: {book_path}")


if __name__ == "__main__":
    main()
