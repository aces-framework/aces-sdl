"""Challenge registry — maps challenge IDs to infrastructure requirements."""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ChallengeInfo:
    """Metadata for a single benchmark challenge."""

    id: str
    category: str
    difficulty: str
    infra_type: str  # "docker" or "static"
    name: str = ""
    port: int | None = None
    ground_truth_flag: str | None = None
    aliases: list[str] = field(default_factory=list)
    path_hint: str | None = None
    target_url: str | None = None


class ChallengeRegistry:
    """Registry of benchmark challenges loaded from YAML config.

    Usage:
        registry = ChallengeRegistry("configs/challenges/cybench.yaml")
        info = registry.get("eval-me")
        url = registry.get_target_url("eval-me")  # -> "http://localhost:32805"
    """

    def __init__(self, config_path: str, target_overrides_path: str | None = None):
        self._challenges: dict[str, ChallengeInfo] = {}
        self._target_overrides: dict[str, str] = {}
        self._load(config_path)
        if target_overrides_path:
            self.load_target_overrides(target_overrides_path)

    @staticmethod
    def _normalize(value: str) -> str:
        """Normalize a challenge identifier/name for fuzzy matching."""
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    @staticmethod
    def _tokenize(value: str) -> set[str]:
        """Tokenize text for loose challenge matching across naming schemes."""
        stop_tokens = {
            "the",
            "a",
            "an",
            "and",
            "id",
            "very",
            "easy",
            "medium",
            "hard",
            "challenge",
            "ctf",
        }
        return {
            tok
            for tok in re.split(r"[^a-z0-9]+", value.lower())
            if tok and tok not in stop_tokens and not tok.isdigit()
        }

    @staticmethod
    def _normalize_target_url(raw_value: Any) -> str | None:
        """Normalize a target URL/endpoint declaration to an absolute HTTP URL."""
        if raw_value is None:
            return None
        if isinstance(raw_value, (int, float)):
            raw = f"http://localhost:{int(raw_value)}"
        else:
            raw = str(raw_value).strip()
        if not raw:
            return None
        if raw.startswith(("http://", "https://")):
            return raw
        if re.fullmatch(r"\d+", raw):
            return f"http://localhost:{raw}"
        if re.fullmatch(r"[^:/\s]+:\d+", raw):
            return f"http://{raw}"
        return raw

    @staticmethod
    def _rewrite_url_host(url: str, host: str) -> str:
        """Rewrite localhost-style URLs for caller-specified host overrides."""
        if "{host}" in url:
            return url.replace("{host}", host)

        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return url
        if host == "localhost":
            return url
        if parsed.hostname not in {"localhost", "127.0.0.1"}:
            return url

        netloc_host = host
        if parsed.username:
            auth = parsed.username
            if parsed.password:
                auth += f":{parsed.password}"
            netloc_host = f"{auth}@{netloc_host}"
        if parsed.port is not None:
            netloc_host = f"{netloc_host}:{parsed.port}"
        return urlunparse(
            (
                parsed.scheme,
                netloc_host,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment,
            )
        )

    def _load(self, config_path: str) -> None:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Challenge registry not found: {config_path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        for entry in data.get("challenges", []):
            aliases = entry.get("aliases", [])
            if aliases is None:
                aliases = []
            if not isinstance(aliases, list):
                aliases = [str(aliases)]
            info = ChallengeInfo(
                id=entry["id"],
                category=entry.get("category", ""),
                difficulty=entry.get("difficulty", ""),
                infra_type=entry.get("infra_type", "static"),
                name=entry.get("name", ""),
                port=entry.get("port"),
                ground_truth_flag=entry.get("ground_truth_flag"),
                aliases=[str(x) for x in aliases],
                path_hint=entry.get("path_hint"),
                target_url=self._normalize_target_url(
                    entry.get("target_url", entry.get("target"))
                ),
            )
            self._challenges[info.id] = info

        logger.info("Loaded %d challenges from %s", len(self._challenges), config_path)

    @staticmethod
    def _extract_target_mapping(payload: Any) -> dict[str, Any]:
        """Extract a challenge_id -> endpoint mapping from common JSON/YAML shapes."""
        if isinstance(payload, list):
            mapping: dict[str, Any] = {}
            for item in payload:
                if not isinstance(item, dict):
                    continue
                cid = (
                    item.get("id") or item.get("challenge_id") or item.get("challenge")
                )
                if not cid:
                    continue
                mapping[str(cid)] = item
            return mapping

        if not isinstance(payload, dict):
            return {}

        # Common wrapper keys used by deployment scripts.
        for key in (
            "challenge_targets",
            "target_overrides",
            "targets",
            "challenge_urls",
        ):
            inner = payload.get(key)
            if isinstance(inner, (dict, list)):
                return ChallengeRegistry._extract_target_mapping(inner)

        # Export shape from scripts can use "challenges": [{id, target_url, ...}]
        challenges = payload.get("challenges")
        if isinstance(challenges, list):
            return ChallengeRegistry._extract_target_mapping(challenges)

        # Assume direct mapping.
        return {str(k): v for k, v in payload.items()}

    @staticmethod
    def _coerce_mapping_value(value: Any) -> str | None:
        if isinstance(value, dict):
            direct = value.get("target_url", value.get("target", value.get("url")))
            normalized = ChallengeRegistry._normalize_target_url(direct)
            if normalized:
                return normalized
            port = value.get("port")
            host = value.get("host", "localhost")
            if port is not None:
                return ChallengeRegistry._normalize_target_url(f"{host}:{int(port)}")
            return None
        return ChallengeRegistry._normalize_target_url(value)

    def set_target_overrides(
        self, mapping: dict[str, Any], strict: bool = False
    ) -> int:
        """Apply target URL overrides keyed by challenge id/name/alias."""
        loaded = 0
        for raw_key, raw_value in mapping.items():
            resolved_id = self.resolve_id(str(raw_key))
            if resolved_id is None:
                if strict:
                    raise KeyError(
                        f"Unknown challenge in target override mapping: {raw_key}"
                    )
                logger.warning(
                    "Ignoring unknown challenge target override key: %s", raw_key
                )
                continue
            target = self._coerce_mapping_value(raw_value)
            if not target:
                if strict:
                    raise ValueError(
                        f"Invalid target override for challenge {raw_key!r}: {raw_value!r}"
                    )
                logger.warning(
                    "Ignoring invalid target override for %s: %r", raw_key, raw_value
                )
                continue
            self._target_overrides[resolved_id] = target
            loaded += 1
        return loaded

    def load_target_overrides(self, path: str, strict: bool = False) -> int:
        """Load challenge target URL overrides from JSON or YAML file."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Target overrides file not found: {path}")
        text = p.read_text()
        payload: Any
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = yaml.safe_load(text)
        mapping = self._extract_target_mapping(payload)
        loaded = self.set_target_overrides(mapping, strict=strict)
        logger.info("Loaded %d challenge target overrides from %s", loaded, path)
        return loaded

    def get_target_overrides(self) -> dict[str, str]:
        return dict(self._target_overrides)

    def resolve_id(self, challenge_id: str) -> str | None:
        """Resolve challenge ID/name/alias to a canonical registry ID."""
        if challenge_id in self._challenges:
            return challenge_id

        query = self._normalize(challenge_id)
        if not query:
            return None

        query_tokens = self._tokenize(challenge_id)
        scores_by_id: dict[str, int] = {}

        for cid, info in self._challenges.items():
            keys = [cid, info.name, *info.aliases]
            for key in keys:
                key_norm = self._normalize(key)
                if not key_norm:
                    continue

                score = 0
                if query == key_norm:
                    score = max(score, 100)
                elif query in key_norm:
                    score = max(score, 88)
                elif key_norm in query:
                    score = max(score, 82)

                key_tokens = self._tokenize(key)
                if query_tokens and key_tokens:
                    overlap = len(query_tokens & key_tokens)
                    if overlap:
                        precision = overlap / len(key_tokens)
                        recall = overlap / len(query_tokens)
                        score = max(score, int(65 + 30 * max(precision, recall)))
                        if key_tokens.issubset(query_tokens):
                            score = max(score, 86 + min(4, len(key_tokens)))
                        if query_tokens.issubset(key_tokens):
                            score = max(score, 84 + min(4, len(query_tokens)))

                if score > scores_by_id.get(cid, 0):
                    scores_by_id[cid] = score

        if not scores_by_id:
            return None

        ranked = sorted(scores_by_id.items(), key=lambda item: item[1], reverse=True)
        best_id, best_score = ranked[0]
        if best_score < 75:
            return None

        # Ambiguity guard: when top candidates are effectively tied, force explicit alias/path_hint.
        if len(ranked) > 1 and ranked[1][1] >= best_score - 2:
            logger.warning(
                "Ambiguous challenge resolution for %r: top candidates=%s",
                challenge_id,
                ranked[:3],
            )
            return None

        return best_id

    def get(self, challenge_id: str) -> ChallengeInfo:
        """Get challenge info by ID. Raises KeyError if not found."""
        resolved_id = self.resolve_id(challenge_id)
        if resolved_id is None:
            raise KeyError(f"Challenge not found: {challenge_id}")
        return self._challenges[resolved_id]

    def list_all(self) -> list[ChallengeInfo]:
        """Return all challenges."""
        return list(self._challenges.values())

    def list_docker_challenges(self) -> list[ChallengeInfo]:
        """Return challenges that need Docker containers."""
        return [c for c in self._challenges.values() if c.infra_type == "docker"]

    def list_static_challenges(self) -> list[ChallengeInfo]:
        """Return file-based challenges (no server needed)."""
        return [c for c in self._challenges.values() if c.infra_type == "static"]

    def get_target_url(self, challenge_id: str, host: str = "localhost") -> str | None:
        """Get the target URL for a challenge, or None for static challenges."""
        info = self.get(challenge_id)
        override = self._target_overrides.get(info.id)
        if override:
            return self._rewrite_url_host(override, host=host)
        if info.target_url:
            return self._rewrite_url_host(info.target_url, host=host)
        if info.infra_type == "docker" and info.port:
            return f"http://{host}:{info.port}"
        return None

    def __len__(self) -> int:
        return len(self._challenges)

    def __contains__(self, challenge_id: str) -> bool:
        return self.resolve_id(challenge_id) is not None
