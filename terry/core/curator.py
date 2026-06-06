"""Self-evolving skill curator - autonomous skill library management.

Inspired by Hermes Agent's Curator, this module automatically grades,
consolidates, and prunes the skill library based on usage patterns.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class SkillsCurator:
    """Autonomous skill library curator.

    Tracks skill usage and effectiveness, suggests new skills from
    conversation patterns, and periodically prunes unused skills.
    """

    def __init__(self, skills_dir: Path | None = None, data_dir: Path | None = None):
        self.skills_dir = skills_dir or Path.cwd() / "skills"
        self.data_dir = data_dir or Path.home() / ".terry" / "curator"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.usage_file = self.data_dir / "skill_usage.json"
        self.usage: dict[str, dict[str, Any]] = {}
        self._load_usage()

    def _load_usage(self) -> None:
        """Load skill usage data."""
        if self.usage_file.exists():
            try:
                self.usage = json.loads(self.usage_file.read_text(encoding="utf-8"))
            except Exception:
                self.usage = {}

    def _save_usage(self) -> None:
        """Save skill usage data."""
        self.usage_file.write_text(
            json.dumps(self.usage, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def record_usage(self, skill_name: str, success: bool = True) -> None:
        """Record a skill being used."""
        now = datetime.now().isoformat()
        if skill_name not in self.usage:
            self.usage[skill_name] = {
                "total_uses": 0,
                "successes": 0,
                "failures": 0,
                "first_used": now,
                "last_used": now,
                "history": [],
            }

        self.usage[skill_name]["total_uses"] += 1
        if success:
            self.usage[skill_name]["successes"] += 1
        else:
            self.usage[skill_name]["failures"] += 1
        self.usage[skill_name]["last_used"] = now
        self.usage[skill_name]["history"].append({
            "timestamp": now,
            "success": success,
        })

        # Keep only last 100 history entries
        if len(self.usage[skill_name]["history"]) > 100:
            self.usage[skill_name]["history"] = \
                self.usage[skill_name]["history"][-100:]

        self._save_usage()

    def get_effectiveness(self, skill_name: str) -> float:
        """Get success rate for a skill (0.0 to 1.0)."""
        if skill_name not in self.usage:
            return 0.0
        total = self.usage[skill_name]["total_uses"]
        if total == 0:
            return 0.0
        return self.usage[skill_name]["successes"] / total

    def get_top_skills(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get the most effective skills."""
        scored = []
        for name, data in self.usage.items():
            eff = data["successes"] / max(data["total_uses"], 1)
            recency = data.get("last_used", "")
            scored.append({
                "name": name,
                "effectiveness": round(eff, 2),
                "total_uses": data["total_uses"],
                "last_used": recency,
            })
        scored.sort(key=lambda s: (s["effectiveness"], s["total_uses"]), reverse=True)
        return scored[:limit]

    def suggest_pruning(self, min_uses: int = 3, max_age_days: int = 30) -> list[str]:
        """Suggest skills that should be pruned.

        Returns list of skill names that have low usage or poor effectiveness.
        """
        now = datetime.now()
        to_prune = []

        for name, data in self.usage.items():
            # Skip built-in skills
            if name in ("code-review", "data-analysis", "document-generator"):
                continue

            uses = data["total_uses"]
            last_used = data.get("last_used", "")

            # Prune if never used successfully and old
            if uses < min_uses:
                if last_used:
                    try:
                        age = now - datetime.fromisoformat(last_used)
                        if age > timedelta(days=max_age_days):
                            to_prune.append(name)
                    except Exception:
                        to_prune.append(name)
                else:
                    to_prune.append(name)

            # Prune if very ineffective
            if uses >= min_uses and self.get_effectiveness(name) < 0.3:
                to_prune.append(name)

        return to_prune

    def suggest_new_skill(
        self, name: str, description: str, triggers: list[str], content: str
    ) -> Path:
        """Create a suggested skill file for review.

        Returns path to the skill file.
        """
        suggested_dir = self.data_dir / "suggested"
        suggested_dir.mkdir(parents=True, exist_ok=True)

        skill_content = (
            f"---\n"
            f"name: {name}\n"
            f"description: {description}\n"
            f"triggers:\n"
            + "".join(f"  - {t}\n" for t in triggers)
            + f"---\n\n"
            f"{content}\n"
        )

        skill_path = suggested_dir / f"{name}.md"
        skill_path.write_text(skill_content, encoding="utf-8")
        return skill_path

    def prune_skills(self, skill_names: list[str]) -> int:
        """Remove specified skills. Returns count removed."""
        removed = 0
        for name in skill_names:
            # Find skill file
            for skill_file in self.skills_dir.rglob("SKILL.md"):
                if skill_file.parent.name == name:
                    try:
                        skill_file.unlink()
                        removed += 1
                    except Exception:
                        pass
            # Clean up usage data
            self.usage.pop(name, None)

        if removed > 0:
            self._save_usage()
        return removed

    def get_cycle_summary(self) -> dict[str, Any]:
        """Get a summary for the 7-day curator cycle."""
        total_uses = sum(d["total_uses"] for d in self.usage.values())
        top = self.get_top_skills(5)
        to_prune = self.suggest_pruning()

        return {
            "skills_tracked": len(self.usage),
            "total_uses": total_uses,
            "top_skills": top,
            "suggested_pruning": to_prune,
            "average_effectiveness": round(
                sum(self.get_effectiveness(n) for n in self.usage) /
                max(len(self.usage), 1),
                2,
            ),
        }
