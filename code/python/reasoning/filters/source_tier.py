"""
Source tier filter for implementing tier-based filtering and content enrichment.
"""

from typing import List, Dict, Any
from core.config import CONFIG


class NoValidSourcesError(Exception):
    """Raised when all sources are filtered out in strict mode."""
    pass


class SourceTierFilter:
    """
    Hard filter implementing tier-based filtering and content enrichment.

    Filters sources based on mode configuration and enriches items
    with tier metadata and prefixes.
    """

    def __init__(self, source_tiers: Dict[str, Dict[str, Any]]):
        """
        Initialize source tier filter.

        Args:
            source_tiers: Dictionary mapping source names to tier info
                         (from CONFIG.reasoning_source_tiers)
        """
        self.source_tiers = source_tiers

    def filter_and_enrich(
        self,
        items: List[Dict[str, Any]],
        mode: str
    ) -> List[Dict[str, Any]]:
        """
        Filter items by source tier and enrich with metadata.

        Args:
            items: List of retrieved items (NLWeb Item format)
            mode: Research mode ("strict", "discovery", or "monitor")

        Returns:
            Filtered and enriched list of items

        Raises:
            NoValidSourcesError: If strict mode filters out all sources
        """
        # Get mode configuration
        mode_config = CONFIG.reasoning_mode_configs.get(mode, {})
        max_tier = mode_config.get("max_tier", 5)

        filtered_items = []

        for item in items:
            # Extract source from item
            source = item.get("site", "").strip()

            # Get tier info
            tier_info = self._get_tier_info(source)
            tier = tier_info["tier"]
            source_type = tier_info["type"]

            # Apply filtering based on mode
            if mode == "strict":
                # Drop tier > max_tier or unknown sources
                if tier > max_tier or tier == 999:
                    continue

            # Enrich item with tier metadata
            enriched_item = self._enrich_item(item, tier, source_type, source)
            filtered_items.append(enriched_item)

        # Check for empty result in strict mode
        if mode == "strict" and not filtered_items:
            raise NoValidSourcesError(
                f"All sources filtered out in strict mode (max_tier={max_tier})"
            )

        return filtered_items

    def _get_tier_info(self, source: str) -> Dict[str, Any]:
        """
        Get tier and type information for a source.

        Args:
            source: Source name

        Returns:
            Dictionary with "tier" and "type" keys
            Unknown sources get tier=999, type="unknown"
        """
        if source in self.source_tiers:
            return self.source_tiers[source]
        else:
            # Unknown source
            return {"tier": 999, "type": "unknown"}

    def _enrich_item(
        self,
        item: Dict[str, Any],
        tier: int,
        source_type: str,
        original_source: str
    ) -> Dict[str, Any]:
        """
        Enrich item with tier metadata and description prefix.

        Args:
            item: Original item
            tier: Source tier (1-5 or 999)
            source_type: Source type (official, news, digital, social, unknown)
            original_source: Original source name

        Returns:
            Enriched item with metadata and tier prefix
        """
        # Create a copy to avoid mutating original
        enriched = item.copy()

        # Add reasoning metadata
        enriched["_reasoning_metadata"] = {
            "tier": tier,
            "type": source_type,
            "original_source": original_source
        }

        # Add tier prefix to description
        tier_prefix = self._get_tier_prefix(tier, source_type)
        original_description = enriched.get("description", "")
        enriched["description"] = f"{tier_prefix} {original_description}".strip()

        return enriched

    def _get_tier_prefix(self, tier: int, source_type: str) -> str:
        """
        Generate tier prefix for content.

        Args:
            tier: Source tier
            source_type: Source type

        Returns:
            Tier prefix string (e.g., "[Tier 1 | official]")
        """
        if tier == 999:
            return "[Tier Unknown | unknown]"
        else:
            return f"[Tier {tier} | {source_type}]"

    def get_tier(self, source: str) -> int:
        """
        Get tier number for a source.

        Args:
            source: Source name

        Returns:
            Tier number (1-5 or 999 for unknown)
        """
        tier_info = self._get_tier_info(source)
        return tier_info["tier"]
