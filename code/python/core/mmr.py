# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
MMR (Maximal Marginal Relevance) Algorithm Implementation

Purpose:
    Diversify search results by balancing relevance and novelty.
    Prevents redundant results by penalizing documents similar to already-selected ones.

Algorithm:
    MMR = λ * Relevance(doc, query) - (1-λ) * max(Similarity(doc, selected_doc))

    Where:
    - λ (lambda): Trade-off parameter between relevance and diversity
      - λ = 1.0: Pure relevance (no diversity)
      - λ = 0.5: Balanced
      - λ = 0.0: Pure diversity (no relevance)
    - Relevance: Document's score from ranking (LLM score, BM25, etc.)
    - Similarity: Cosine similarity between document vectors

References:
    Carbonell, J., & Goldstein, J. (1998). "The use of MMR, diversity-based
    reranking for reordering documents and producing summaries."
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("mmr")


class MMRReranker:
    """
    Maximal Marginal Relevance (MMR) re-ranker for diversifying search results.
    """

    def __init__(self, lambda_param: float = 0.7, query: str = ""):
        """
        Initialize MMR re-ranker.

        Args:
            lambda_param: Trade-off between relevance and diversity (0.0 to 1.0)
                         Higher λ = more relevance, lower λ = more diversity
            query: The user's query (for intent detection)
        """
        self.lambda_param = lambda_param
        self.query = query
        self.detected_intent = "BALANCED"  # Will be updated by intent detection

        # Intent-based λ adjustment
        self.lambda_param = self._detect_intent_and_adjust_lambda(query)

        logger.info(f"MMR initialized with λ={self.lambda_param:.2f}")

    def _detect_intent_and_adjust_lambda(self, query: str) -> float:
        """
        Detect query intent and adjust λ accordingly.

        Intent types:
        - SPECIFIC: User wants precise results (higher λ, less diversity)
        - EXPLORATORY: User wants diverse results (lower λ, more diversity)
        - BALANCED: Default mixed intent

        Args:
            query: User's search query

        Returns:
            Adjusted lambda value
        """
        if not query:
            return self.lambda_param

        query_lower = query.lower()

        # SPECIFIC intent indicators (prioritize relevance)
        specific_indicators = [
            'how to', '如何', '怎麼', '怎么',  # How-to queries
            'what is', '什麼是', '什么是',     # Definition queries
            'where', '哪裡', '哪里',           # Location queries
            'when', '什麼時候', '什么时候',    # Time queries
        ]

        # EXPLORATORY intent indicators (prioritize diversity)
        exploratory_indicators = [
            'best', '最好', '推薦', '推荐',    # Recommendation queries
            'ideas', '點子', '想法',           # Brainstorming
            'options', '選項', '选项',         # Comparison shopping
            'alternatives', '替代', '其他',    # Alternative seeking
            'trends', '趨勢', '趋势',          # Trend exploration
            'popular', '熱門', '热门',         # Popularity queries
            'methods', 'ways', '方法', '方式', # Method/approach queries
        ]

        specific_score = sum(1 for indicator in specific_indicators if indicator in query_lower)
        exploratory_score = sum(1 for indicator in exploratory_indicators if indicator in query_lower)

        # Adjust lambda based on intent
        if specific_score > exploratory_score:
            # SPECIFIC: Higher λ (0.8) - prioritize relevance
            adjusted_lambda = 0.8
            self.detected_intent = "SPECIFIC"
            print(f"[MMR INTENT] SPECIFIC query detected - λ adjusted to {adjusted_lambda}")
            logger.info(f"[INTENT] SPECIFIC query detected - λ adjusted to {adjusted_lambda}")
        elif exploratory_score > specific_score:
            # EXPLORATORY: Lower λ (0.5) - prioritize diversity
            adjusted_lambda = 0.5
            self.detected_intent = "EXPLORATORY"
            print(f"[MMR INTENT] EXPLORATORY query detected - λ adjusted to {adjusted_lambda}")
            logger.info(f"[INTENT] EXPLORATORY query detected - λ adjusted to {adjusted_lambda}")
        else:
            # BALANCED: Use default λ
            adjusted_lambda = self.lambda_param
            self.detected_intent = "BALANCED"
            print(f"[MMR INTENT] BALANCED query - λ remains {adjusted_lambda}")
            logger.info(f"[INTENT] BALANCED query - λ remains {adjusted_lambda}")

        return adjusted_lambda

    def _log_diversity_metrics(self, avg_orig_sim: float, avg_mmr_sim: float, diversity_reduction: float) -> None:
        """
        Log diversity improvement metrics to algo/mmr_metrics.log

        Args:
            avg_orig_sim: Average similarity before MMR
            avg_mmr_sim: Average similarity after MMR
            diversity_reduction: Improvement (orig - mmr)
        """
        try:
            from pathlib import Path
            from datetime import datetime

            # Create algo directory if it doesn't exist
            algo_dir = Path("algo")
            algo_dir.mkdir(exist_ok=True)

            log_file = algo_dir / "mmr_metrics.log"

            # Prepare log entry
            timestamp = datetime.now().isoformat()
            log_entry = (
                f"{timestamp} | "
                f"Query: {self.query[:50]:<50} | "
                f"Intent: {self.detected_intent:<12} | "
                f"λ: {self.lambda_param:.2f} | "
                f"Similarity: {avg_orig_sim:.3f} → {avg_mmr_sim:.3f} | "
                f"Reduction: {diversity_reduction:.3f}\n"
            )

            # Append to log file
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)

            logger.debug(f"Logged diversity metrics to {log_file}")

        except Exception as e:
            logger.error(f"Failed to log diversity metrics: {e}")

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score (0 to 1)
        """
        try:
            # Convert to numpy arrays
            v1 = np.array(vec1)
            v2 = np.array(vec2)

            # Calculate cosine similarity
            dot_product = np.dot(v1, v2)
            norm_v1 = np.linalg.norm(v1)
            norm_v2 = np.linalg.norm(v2)

            if norm_v1 == 0 or norm_v2 == 0:
                return 0.0

            similarity = dot_product / (norm_v1 * norm_v2)

            # Clamp to [0, 1] range (cosine can be -1 to 1, but for embeddings it's typically 0-1)
            return max(0.0, min(1.0, float(similarity)))

        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0

    def rerank(self,
               ranked_results: List[Dict[str, Any]],
               query_vector: Optional[List[float]] = None,
               top_k: int = 10) -> Tuple[List[Dict[str, Any]], List[float]]:
        """
        Apply MMR re-ranking to diversify results.

        Args:
            ranked_results: List of ranked documents with 'ranking' scores and 'vector' embeddings
            query_vector: Optional query embedding (not used in current implementation)
            top_k: Number of results to return

        Returns:
            Tuple of (reranked_results, mmr_scores)
        """
        if not ranked_results:
            logger.warning("No results to rerank")
            return [], []

        # Filter results that have vectors
        candidates = [r for r in ranked_results if 'vector' in r and r['vector'] is not None]

        if len(candidates) == 0:
            logger.warning("No results with vectors available for MMR")
            return ranked_results[:top_k], [0.0] * min(top_k, len(ranked_results))

        if len(candidates) <= 3:
            logger.info(f"Only {len(candidates)} results with vectors, skipping MMR")
            return ranked_results[:top_k], [0.0] * min(top_k, len(ranked_results))

        logger.info(f"Applying MMR to {len(candidates)} results")

        # Normalize ranking scores to [0, 1] for MMR calculation
        scores = [r['ranking'].get('score', 0) for r in candidates]
        max_score = max(scores) if scores else 1.0
        min_score = min(scores) if scores else 0.0
        score_range = max_score - min_score if max_score != min_score else 1.0

        # Initialize
        selected_results = []
        selected_indices = set()
        mmr_scores = []

        # Select first result (highest relevance score)
        first_idx = 0
        selected_results.append(candidates[first_idx])
        selected_indices.add(first_idx)

        # Normalized relevance score for first item
        normalized_relevance = (candidates[first_idx]['ranking'].get('score', 0) - min_score) / score_range
        mmr_scores.append(normalized_relevance)

        print(f"[MMR] Selected 1st: {candidates[first_idx]['name'][:50]} (score={candidates[first_idx]['ranking'].get('score', 0):.1f})")
        logger.debug(f"[MMR] Selected 1st: {candidates[first_idx]['name'][:50]} (score={candidates[first_idx]['ranking'].get('score', 0):.1f})")

        # Iteratively select remaining results
        for iteration in range(1, min(top_k, len(candidates))):
            best_mmr_score = -float('inf')
            best_idx = None

            # Evaluate each unselected candidate
            for idx, candidate in enumerate(candidates):
                if idx in selected_indices:
                    continue

                # Calculate relevance score (normalized)
                relevance = (candidate['ranking'].get('score', 0) - min_score) / score_range

                # Calculate max similarity to already-selected documents
                max_similarity = 0.0
                for selected in selected_results:
                    similarity = self.cosine_similarity(candidate['vector'], selected['vector'])
                    max_similarity = max(max_similarity, similarity)

                # MMR formula: λ * relevance - (1-λ) * max_similarity
                mmr_score = self.lambda_param * relevance - (1 - self.lambda_param) * max_similarity

                if mmr_score > best_mmr_score:
                    best_mmr_score = mmr_score
                    best_idx = idx

            if best_idx is not None:
                selected_results.append(candidates[best_idx])
                selected_indices.add(best_idx)
                mmr_scores.append(best_mmr_score)

                print(f"[MMR] Selected {iteration + 1}th: {candidates[best_idx]['name'][:50]} (mmr={best_mmr_score:.3f}, score={candidates[best_idx]['ranking'].get('score', 0):.1f})")
                logger.debug(f"[MMR] Selected {iteration + 1}th: {candidates[best_idx]['name'][:50]} "
                           f"(mmr={best_mmr_score:.3f}, score={candidates[best_idx]['ranking'].get('score', 0):.1f})")

        # Log diversity improvement
        if len(selected_results) >= 2:
            # Calculate average similarity before MMR (top-k results)
            original_top_k = candidates[:top_k]
            original_similarities = []
            for i in range(len(original_top_k)):
                for j in range(i + 1, len(original_top_k)):
                    sim = self.cosine_similarity(original_top_k[i]['vector'], original_top_k[j]['vector'])
                    original_similarities.append(sim)

            # Calculate average similarity after MMR
            mmr_similarities = []
            for i in range(len(selected_results)):
                for j in range(i + 1, len(selected_results)):
                    sim = self.cosine_similarity(selected_results[i]['vector'], selected_results[j]['vector'])
                    mmr_similarities.append(sim)

            avg_orig_sim = np.mean(original_similarities) if original_similarities else 0.0
            avg_mmr_sim = np.mean(mmr_similarities) if mmr_similarities else 0.0
            diversity_reduction = avg_orig_sim - avg_mmr_sim

            print(f"[MMR] Diversity improvement: avg similarity {avg_orig_sim:.3f} → {avg_mmr_sim:.3f} (reduction: {diversity_reduction:.3f})")
            logger.info(f"[MMR] Diversity improvement: avg similarity {avg_orig_sim:.3f} → {avg_mmr_sim:.3f} "
                       f"(reduction: {diversity_reduction:.3f})")

            # Log diversity metrics to algo/mmr_metrics.log
            self._log_diversity_metrics(avg_orig_sim, avg_mmr_sim, diversity_reduction)

        # Fill remaining slots with non-vector results if needed
        non_vector_results = [r for r in ranked_results if 'vector' not in r or r['vector'] is None]
        remaining_count = top_k - len(selected_results)
        if remaining_count > 0 and non_vector_results:
            selected_results.extend(non_vector_results[:remaining_count])
            mmr_scores.extend([0.0] * min(remaining_count, len(non_vector_results)))

        return selected_results, mmr_scores
