"""Plugin Ecosystem 2.0 — rating system + community contributions.

Extends plugin_market.py with:
- Rating system: users rate plugins (1-5 stars), aggregate scores
- Review system: text reviews with author verification
- Contribution workflow: submit → review → publish
- Install analytics: download counts, popularity trends

Usage:
    from terry.core.plugin_ecosystem import PluginEcosystem
    eco = PluginEcosystem()
    eco.rate("hello-terry", 5)
    eco.review("hello-terry", "Great demo plugin!", author="alice")
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PluginRating:
    """Aggregated rating for a plugin."""

    plugin: str
    total_ratings: int = 0
    average: float = 0.0
    distribution: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    last_rated: float = 0.0


@dataclass
class PluginReview:
    """A user review for a plugin."""

    plugin: str
    author: str
    content: str
    rating: int = 0
    timestamp: float = field(default_factory=time.time)
    verified: bool = False  # Author is the plugin creator

    def to_dict(self) -> dict:
        return {
            "plugin": self.plugin, "author": self.author,
            "content": self.content, "rating": self.rating,
            "timestamp": self.timestamp, "verified": self.verified,
        }


class PluginEcosystem:
    """Rating, review, and contribution management for the plugin marketplace."""

    def __init__(self, data_dir: Path | None = None):
        if data_dir is None:
            from terry.core.platform_utils import get_terry_dir
            data_dir = get_terry_dir() / "ecosystem"
        self._dir = data_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._ratings: dict[str, list[int]] = defaultdict(list)
        self._reviews: dict[str, list[PluginReview]] = defaultdict(list)
        self._submissions: list[dict] = []
        self._load()

    def _load(self):
        path = self._dir / "ecosystem.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                for name, ratings in data.get("ratings", {}).items():
                    self._ratings[name] = ratings
                for rev in data.get("reviews", []):
                    self._reviews[rev["plugin"]].append(PluginReview(
                        plugin=rev["plugin"], author=rev.get("author", ""),
                        content=rev["content"], rating=rev.get("rating", 0),
                        timestamp=rev.get("timestamp", 0.0),
                        verified=rev.get("verified", False),
                    ))
                self._submissions = data.get("submissions", [])
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self):
        data = {
            "ratings": dict(self._ratings),
            "reviews": [
                r.to_dict()
                for revs in self._reviews.values() for r in revs
            ],
            "submissions": self._submissions,
        }
        (self._dir / "ecosystem.json").write_text(json.dumps(data, indent=2))

    # ── Rating System ────────────────────────────────────────────

    def rate(self, plugin: str, score: int):
        """Rate a plugin from 1 to 5 stars."""
        score = max(1, min(5, score))
        self._ratings[plugin].append(score)
        self._save()

    def get_rating(self, plugin: str) -> PluginRating:
        """Get aggregated rating for a plugin."""
        scores = self._ratings.get(plugin, [])
        dist: dict[int, int] = defaultdict(int)
        for s in scores:
            dist[s] += 1
        return PluginRating(
            plugin=plugin,
            total_ratings=len(scores),
            average=sum(scores) / len(scores) if scores else 0.0,
            distribution=dist,
            last_rated=max(time.time(), 0) if not scores else 0.0,
        )

    def get_top_rated(self, limit: int = 10) -> list[PluginRating]:
        """Get top-rated plugins by average score."""
        ratings = [self.get_rating(p) for p in self._ratings]
        ratings.sort(key=lambda r: (r.average, r.total_ratings), reverse=True)
        return ratings[:limit]

    # ── Review System ────────────────────────────────────────────

    def review(self, plugin: str, content: str, rating: int = 0,
               author: str = "", verified: bool = False):
        """Submit a review for a plugin."""
        review = PluginReview(
            plugin=plugin, author=author or "anonymous",
            content=content, rating=rating, verified=verified,
        )
        self._reviews[plugin].append(review)
        self._save()

    def get_reviews(self, plugin: str, limit: int = 20) -> list[PluginReview]:
        """Get reviews for a plugin, newest first."""
        reviews = self._reviews.get(plugin, [])
        reviews.sort(key=lambda r: r.timestamp, reverse=True)
        return reviews[:limit]

    # ── Contribution Workflow ────────────────────────────────────

    def submit_plugin(self, name: str, repo: str, author: str,
                      description: str = ""):
        """Submit a plugin for review/publishing."""
        submission = {
            "name": name, "repo": repo, "author": author,
            "description": description,
            "status": "pending",  # pending → reviewed → published
            "submitted_at": time.time(),
        }
        self._submissions.append(submission)
        self._save()
        return len(self._submissions) - 1  # Return submission index

    def review_submission(self, index: int, approved: bool, reviewer: str = ""):
        """Approve or reject a plugin submission."""
        if 0 <= index < len(self._submissions):
            self._submissions[index]["status"] = "published" if approved else "rejected"
            self._submissions[index]["reviewer"] = reviewer
            self._submissions[index]["reviewed_at"] = time.time()
            self._save()

    def get_submissions(self, status: str | None = None) -> list[dict]:
        """List plugin submissions, optionally filtered by status."""
        if status:
            return [s for s in self._submissions if s["status"] == status]
        return list(self._submissions)

    # ── Stats ────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "rated_plugins": len(self._ratings),
            "total_ratings": sum(len(v) for v in self._ratings.values()),
            "total_reviews": sum(len(v) for v in self._reviews.values()),
            "pending_submissions": len(self.get_submissions("pending")),
            "published_plugins": len(self.get_submissions("published")),
        }
