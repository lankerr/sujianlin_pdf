from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Post:
    """Metadata for a Scientific Spaces article."""

    title: str
    url: str
    date: date
    # 站点原生分类 slug（如 Big-Data / Mathematics），可属多个
    categories: tuple[str, ...] = ()
    # 主题分类 topic_id（由 taxonomy.classify_title 计算）
    topic: str = ""

    @property
    def primary_category(self) -> str:
        """按抓取优先级返回主原生分类 slug。"""
        from .taxonomy import CRAWL_PRIORITY

        for slug in CRAWL_PRIORITY:
            if slug in self.categories:
                return slug
        return self.categories[0] if self.categories else ""
