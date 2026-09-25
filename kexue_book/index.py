"""按主题输出文章索引（Markdown + JSON）与统计。"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

from .taxonomy import NATIVE_CATEGORIES, topic_name
from .types import Post


def group_by_topic(posts: Iterable[Post]) -> dict[str, list[Post]]:
    """按 topic 分组；组内保持传入顺序（默认按日期升序）。"""
    grouped: dict[str, list[Post]] = {}
    for post in posts:
        grouped.setdefault(post.topic or "misc", []).append(post)
    return grouped


def print_topic_stats(grouped: dict[str, list[Post]]) -> None:
    total = sum(len(posts) for posts in grouped.values())
    print(f"[index] 主题统计（共 {len(grouped)} 个主题，{total} 篇）：")
    for topic_id in sorted(grouped, key=lambda t: -len(grouped[t])):
        print(f"  {topic_name(topic_id):<14s} · {len(grouped[topic_id]):>4d} 篇")


def load_posts_from_json(path: Path) -> list[Post]:
    """读取 write_posts_json / reclassify 产出的 posts_all.json。"""
    data = json.loads(path.read_text(encoding="utf-8"))
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
    by_url: dict[str, Post] = {post.url: post for post in posts}
    return sorted(by_url.values(), key=lambda p: (p.date, p.url))


def write_posts_json(posts: list[Post], path: Path) -> None:
    """写出全量文章元数据（含未入选主题的文章），用于调规则/复盘。"""
    grouped = group_by_topic(posts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total": len(posts),
                "topics": {
                    topic_id: [
                        {
                            "title": post.title,
                            "url": post.url,
                            "date": post.date.isoformat(),
                            "categories": list(post.categories),
                        }
                        for post in grouped[topic_id]
                    ]
                    for topic_id in sorted(grouped)
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"[index] 已写出: {path}")


def write_topic_index(
    posts: Iterable[Post],
    out_dir: Path,
    topic_order: Iterable[str] | None = None,
) -> tuple[Path, Path]:
    """写出主题索引 index.md 与 posts.json，返回两个文件路径。"""
    posts = list(posts)
    grouped = group_by_topic(posts)

    order = list(topic_order) if topic_order else sorted(
        grouped, key=lambda t: -len(grouped[t])
    )
    order += [t for t in grouped if t not in order]

    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "index.md"
    json_path = out_dir / "posts.json"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        "# 苏剑林博客 · 主题索引",
        "",
        f"> 生成时间：{now}；共 {len(posts)} 篇，{len(grouped)} 个主题。",
        "> 来源：科学空间 https://spaces.ac.cn （CC BY-NC-SA，仅供个人学习）",
        "",
    ]

    for topic_id in order:
        topic_posts = grouped.get(topic_id, [])
        if not topic_posts:
            continue
        date_range = (
            f"{topic_posts[0].date.isoformat()} ~ {topic_posts[-1].date.isoformat()}"
            if topic_posts
            else ""
        )
        lines.append(f"## {topic_name(topic_id)} · {len(topic_posts)} 篇（{date_range}）")
        lines.append("")
        lines.append("| # | 日期 | 标题 | 原生分类 |")
        lines.append("|---|------|------|----------|")
        for i, post in enumerate(topic_posts, start=1):
            natives = "、".join(
                NATIVE_CATEGORIES.get(slug).name if NATIVE_CATEGORIES.get(slug) else slug
                for slug in post.categories
            )
            lines.append(
                f"| {i} | {post.date.isoformat()} | [{post.title}]({post.url}) | {natives} |"
            )
        lines.append("")

    index_path.write_text("\n".join(lines), encoding="utf-8")

    json_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total": len(posts),
                "topics": {
                    topic_id: [
                        {
                            "title": post.title,
                            "url": post.url,
                            "date": post.date.isoformat(),
                            "categories": list(post.categories),
                        }
                        for post in grouped[topic_id]
                    ]
                    for topic_id in order
                    if grouped.get(topic_id)
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print_topic_stats(grouped)
    print(f"[index] 已写出: {index_path}")
    print(f"[index] 已写出: {json_path}")
    return index_path, json_path
