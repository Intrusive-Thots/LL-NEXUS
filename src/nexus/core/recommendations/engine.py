"""Recommendation engine — deterministic, explainable champion ranking.

Pipeline (spec §11):

    User Preferences → Base Priority → Current Role → Champion Availability
    → Recent History → Optional Match Context → Final Recommendation

Every result carries an explicit list of reasons derived from the *same* data
used to compute the ranking. The engine never invents reasoning: if a factor
did not influence the decision it does not appear in `reasons`.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from ..champions.models import Champion, ChampionCatalog
from ..champions.priority import PriorityList
from ..state.models import LeagueSnapshot, Role


@dataclass(frozen=True)
class CandidateScore:
    champion: Champion
    score: float
    priority_rank: Optional[int]
    reasons: tuple[str, ...]
    excluded: bool = False
    exclusion_reason: Optional[str] = None
    factors: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Recommendation:
    winner: Optional[CandidateScore]
    ranked: tuple[CandidateScore, ...]          # eligible candidates, best first
    alternates: tuple[CandidateScore, ...]      # next-best picks after winner
    role: Role
    evaluated_at: float
    context_summary: tuple[str, ...]

    @property
    def top_names(self) -> list[str]:
        return [c.champion.name for c in self.ranked[:5]]

    def explanation(self) -> list[str]:
        """Human-readable 'Why?' block for the UI / timeline / sessions."""
        if not self.winner:
            return ["No eligible champion available."]
        lines = [f"Recommendation: {self.winner.champion.name}"]
        for i, r in enumerate(self.winner.reasons, start=1):
            lines.append(f"{i}. {r}")
        return lines


# Score weights — kept as module constants so tests can assert determinism.
W_PRIORITY = 1000.0     # dominant: user intent wins over everything else
W_PREFERRED = 60.0
W_ROLE_MATCH = 40.0
W_NOT_RECENT = 25.0
W_UNRATED_TIEBREAK = 5.0
W_MATCH_ADJUST = 10.0   # per point of contextual adjustment


class RecommendationEngine:
    def __init__(self, catalog: ChampionCatalog, priorities: PriorityList,
                 match_adjustments: Optional[dict[str, float]] = None) -> None:
        self._catalog = catalog
        self._priorities = priorities
        #: optional matchup table {champion_key: +N}; supplied by caller only
        #: when real matchup data exists. Never guessed.
        self._match_adjustments = dict(match_adjustments or {})

    @property
    def catalog(self) -> ChampionCatalog:
        return self._catalog

    @property
    def priorities(self) -> PriorityList:
        return self._priorities

    # ------------------------------------------------------------------ core
    def recommend(self, snapshot: LeagueSnapshot,
                  unavailable_keys: Optional[set[str]] = None,
                  now: Optional[float] = None) -> Recommendation:
        now = now if now is not None else time.time()
        unavailable_keys = unavailable_keys or set()
        role = snapshot.role if snapshot.role is not Role.NONE else Role.NONE
        role_str = role.value if role is not Role.NONE else None

        context: list[str] = []
        context.append(f"Role: {role.display}" if role is not Role.NONE
                       else "Role: not yet assigned")
        context.append(f"Queue: {snapshot.queue_type}" if snapshot.queue_type
                       else "Queue: unknown")
        taken_ids = set(snapshot.banned_ids) | set(snapshot.ally_pick_ids) | set(snapshot.enemy_pick_ids)
        if taken_ids:
            context.append(f"{len(taken_ids)} champions already off the board")

        scored: list[CandidateScore] = []
        for champ in self._catalog.all:
            pref = self._priorities.get(champ.key)
            reasons: list[str] = []
            factors: dict[str, float] = {}
            excluded = False
            exclusion: Optional[str] = None

            if pref and pref.never_pick:
                excluded, exclusion = True, "marked Never Pick"
            elif pref and pref.disabled:
                excluded, exclusion = True, "temporarily disabled"
            elif champ.key in unavailable_keys:
                excluded, exclusion = True, "not available this game"
            elif champ.id in taken_ids:
                excluded, exclusion = True, "already banned or picked"

            if excluded:
                scored.append(CandidateScore(champion=champ, score=float("-inf"),
                                             priority_rank=pref.priority if pref else None,
                                             reasons=tuple(reasons), excluded=True,
                                             exclusion_reason=exclusion, factors={}))
                continue

            score = 0.0
            rank = pref.priority if pref else None
            if rank is not None:
                contribution = W_PRIORITY / rank
                score += contribution
                factors["priority"] = contribution
                reasons.append(f"Highest available priority (#{rank})"
                               if rank == 1 else f"Priority #{rank}")
            else:
                score += W_UNRATED_TIEBREAK
                factors["unrated"] = W_UNRATED_TIEBREAK
                reasons.append("Unrated fallback candidate")

            role_matches = False
            if role_str:
                effective_role = (pref.role_override.upper()
                                  if pref and pref.role_override else None)
                if effective_role == role_str or role_str in champ.upper_roles:
                    role_matches = True
                    score += W_ROLE_MATCH
                    factors["role"] = W_ROLE_MATCH
                    reasons.append(f"{role.display} role matched")
                else:
                    score -= W_ROLE_MATCH
                    factors["role"] = -W_ROLE_MATCH
                    reasons.append(f"Off-role for {role.display}")

            if pref and pref.preferred:
                score += W_PREFERRED
                factors["preferred"] = W_PREFERRED
                reasons.append("Preferred champion")

            if pref:
                pref.prune_recent(now)
                if not pref.recently_played:
                    score += W_NOT_RECENT
                    factors["recent"] = W_NOT_RECENT
                    reasons.append("Not recently played")
                else:
                    reasons.append("Recently played — deprioritised")

            adjust = self._match_adjustments.get(champ.key)
            if adjust:
                score += adjust * W_MATCH_ADJUST
                factors["match"] = adjust * W_MATCH_ADJUST
                reasons.append(f"Match adjustment {'+' if adjust > 0 else ''}{adjust:g}")

            scored.append(CandidateScore(champion=champ, score=score,
                                         priority_rank=rank,
                                         reasons=tuple(reasons), factors=factors))

        eligible = [c for c in scored if not c.excluded]
        # Deterministic ordering: score desc, then priority rank asc, then name.
        eligible.sort(key=lambda c: (-c.score,
                                     c.priority_rank if c.priority_rank is not None else 9999,
                                     c.champion.name.casefold()))
        winner = eligible[0] if eligible else None
        alternates = tuple(eligible[1:4])
        return Recommendation(winner=winner, ranked=tuple(eligible),
                              alternates=alternates, role=role,
                              evaluated_at=now,
                              context_summary=tuple(context))
