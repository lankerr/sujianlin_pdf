"""从已抓取的全量元数据重新归类，生成主题索引。

分类规则调整后（kexue_book/taxonomy.py），用本脚本离线重跑即可，
不需要重新爬取站点：

    python scripts/reclassify.py output/posts_all.json --out output

可选 --topic / --all-topics 与 cli 一致。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kexue_book.index import write_topic_index  # noqa: E402
from kexue_book.taxonomy import resolve_topic_ids  # noqa: E402
from kexue_book.types import Post  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("posts_json", type=Path, help="crawl 产出的 posts_all.json")
    parser.add_argument("--out", type=Path, default=Path("output"), help="输出目录")
    parser.add_argument("--topic", action="append", default=None, help="同 cli 的 --topic")
    parser.add_argument("--all-topics", action="store_true", help="保留全部主题")
    args = parser.parse_args()

    data = json.loads(args.posts_json.read_text(encoding="utf-8"))
    posts: list[Post] = []
    for _topic, entries in data.get("topics", {}).items():
        for entry in entries:
            posts.append(
                Post(
                    title=entry["title"],
                    url=entry["url"],
                    date=date.fromisoformat(entry["date"]),
                    categories=tuple(entry.get("categories", ())),
                )
            )

    # 去重（同一 URL 只保留一次）后按日期排序
    by_url: dict[str, Post] = {post.url: post for post in posts}
    posts = sorted(by_url.values(), key=lambda p: (p.date, p.url))

    # 用当前规则重新归类（在 classify_title 之前需要主分类）
    from kexue_book.taxonomy import classify_title

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

    selected = resolve_topic_ids(args.topic, all_topics=args.all_topics)
    kept = [post for post in posts if post.topic in selected]
    print(f"[reclassify] 全部 {len(posts)} 篇，入选主题 {len(kept)} 篇")

    write_topic_index(kept, args.out, topic_order=selected)
    # 全量元数据同步更新
    from kexue_book.index import write_posts_json

    write_posts_json(posts, args.out / "posts_all.json")


if __name__ == "__main__":
    main()
