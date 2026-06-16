import html
import re
import xml.etree.ElementTree as ET
from datetime import UTC
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

import requests


class NewsService:
    def fetch_entries(
        self,
        sources: list[str],
        keywords: Optional[list[str]] = None,
        max_items: int = 25,
        timeout: int = 20,
        blocked_terms: Optional[list[str]] = None,
        max_age_hours: Optional[int] = None,
        scoring_weights: Optional[dict] = None,
    ) -> list[dict]:
        keywords = [str(keyword).strip().lower() for keyword in (keywords or []) if str(keyword).strip()]
        blocked_terms = [str(term).strip().lower() for term in (blocked_terms or []) if str(term).strip()]
        entries = []
        seen = set()
        now = self._utc_now()
        scoring_weights = self._normalize_scoring_weights(scoring_weights)

        for source in sources:
            source = str(source).strip()
            if not source:
                continue

            try:
                response = requests.get(source, timeout=timeout, headers={"User-Agent": "MoneyPrinter/2.0"})
                response.raise_for_status()
            except Exception:
                continue

            parsed_entries = self._parse_feed(response.text, source)
            for entry in parsed_entries:
                dedupe_key = (entry.get("link") or entry.get("title") or "").strip().lower()
                if not dedupe_key or dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                if self._contains_blocked_term(entry, blocked_terms):
                    continue
                if self._is_too_old(entry, max_age_hours, now):
                    continue

                entry["score"] = self._score_entry(entry, keywords, now, scoring_weights)
                entries.append(entry)

        entries.sort(
            key=lambda item: (
                item.get("score", 0),
                item.get("published_at") or "",
            ),
            reverse=True,
        )
        return entries[:max_items]

    def _parse_feed(self, xml_text: str, source_url: str) -> list[dict]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        items = []
        for item in root.findall(".//item"):
            parsed = self._parse_rss_item(item, source_url)
            if parsed:
                items.append(parsed)

        if items:
            return items

        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall(".//atom:entry", namespace):
            parsed = self._parse_atom_entry(entry, source_url, namespace)
            if parsed:
                items.append(parsed)

        return items

    def _parse_rss_item(self, item, source_url: str) -> Optional[dict]:
        title = self._clean_text(self._text_of(item.find("title")))
        link = self._clean_text(self._text_of(item.find("link")))
        summary = self._clean_text(self._text_of(item.find("description")))
        published_at = self._normalize_datetime(self._text_of(item.find("pubDate")))

        if not title:
            return None

        return {
            "title": title,
            "link": link,
            "summary": summary,
            "published_at": published_at,
            "source_url": source_url,
            "source_type": "rss",
        }

    def _parse_atom_entry(self, entry, source_url: str, namespace: dict) -> Optional[dict]:
        title = self._clean_text(self._text_of(entry.find("atom:title", namespace)))
        summary = self._clean_text(
            self._text_of(entry.find("atom:summary", namespace))
            or self._text_of(entry.find("atom:content", namespace))
        )
        updated = self._text_of(entry.find("atom:updated", namespace))
        published = self._text_of(entry.find("atom:published", namespace))

        link = ""
        link_element = entry.find("atom:link", namespace)
        if link_element is not None:
            link = self._clean_text(link_element.attrib.get("href", ""))

        if not title:
            return None

        return {
            "title": title,
            "link": link,
            "summary": summary,
            "published_at": self._normalize_datetime(published or updated),
            "source_url": source_url,
            "source_type": "atom",
        }

    def _normalize_scoring_weights(self, scoring_weights: Optional[dict]) -> dict:
        defaults = {
            "title_keyword_weight": 5,
            "summary_keyword_weight": 2,
            "has_summary_weight": 1,
            "has_published_at_weight": 1,
            "recency_weight": 1,
        }
        if not isinstance(scoring_weights, dict):
            return defaults

        normalized = defaults.copy()
        for key, default_value in defaults.items():
            try:
                normalized[key] = max(0, int(scoring_weights.get(key, default_value)))
            except (TypeError, ValueError):
                normalized[key] = default_value
        return normalized

    def _score_entry(
        self,
        entry: dict,
        keywords: list[str],
        now: datetime,
        scoring_weights: dict,
    ) -> int:
        title = str(entry.get("title", "")).lower()
        summary = str(entry.get("summary", "")).lower()
        haystack = f"{title} {summary}".lower()
        score = 0

        for keyword in keywords:
            if keyword and keyword in title:
                score += scoring_weights["title_keyword_weight"]
            elif keyword and keyword in haystack:
                score += scoring_weights["summary_keyword_weight"]

        if entry.get("summary"):
            score += scoring_weights["has_summary_weight"]
        if entry.get("published_at"):
            score += scoring_weights["has_published_at_weight"]
            score += self._recency_score(entry.get("published_at"), now) * scoring_weights["recency_weight"]

        return score

    def _contains_blocked_term(self, entry: dict, blocked_terms: list[str]) -> bool:
        if not blocked_terms:
            return False

        haystack = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
        return any(term in haystack for term in blocked_terms if term)

    def _is_too_old(self, entry: dict, max_age_hours: Optional[int], now: datetime) -> bool:
        if not max_age_hours:
            return False

        published_at = self._parse_iso_datetime(entry.get("published_at"))
        if published_at is None:
            return False

        age_hours = (now - published_at).total_seconds() / 3600
        return age_hours > max_age_hours

    def _recency_score(self, published_at: str, now: datetime) -> int:
        parsed = self._parse_iso_datetime(published_at)
        if parsed is None:
            return 0

        age_hours = max(0, (now - parsed).total_seconds() / 3600)
        if age_hours <= 6:
            return 5
        if age_hours <= 24:
            return 4
        if age_hours <= 72:
            return 2
        if age_hours <= 168:
            return 1
        return 0

    def _parse_iso_datetime(self, raw_value: str | None) -> datetime | None:
        value = str(raw_value or "").strip()
        if not value:
            return None

        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except Exception:
            return None

    def _normalize_datetime(self, raw_value: str) -> str | None:
        value = str(raw_value or "").strip()
        if not value:
            return None

        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        except Exception:
            pass

        for candidate in [value.replace("Z", "+00:00"), value]:
            try:
                parsed = datetime.fromisoformat(candidate)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                return parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
            except Exception:
                continue

        return None

    def _utc_now(self) -> datetime:
        return datetime.now(UTC)

    def _clean_text(self, value: str) -> str:
        text = html.unescape(str(value or ""))
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _text_of(self, element) -> str:
        if element is None:
            return ""
        return "".join(element.itertext()).strip()
