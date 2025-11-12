# ML Features Mapping: Logging Fields → Model Training Purpose

## Overview
This document maps each analytics logging field to its specific ML training purpose for BM25, MMR, and XGBoost models.

---

## Table 1: `queries` - Query Metadata

### Existing Fields (Schema v1)

| Field | Data Type | ML Model | Training Purpose | Feature Type |
|-------|-----------|----------|------------------|--------------|
| `query_id` | TEXT | All | **Identifier** - Groups query-document pairs | Key |
| `timestamp` | REAL | XGBoost | **Temporal feature** - Query time (hour/day/week patterns) | Context |
| `user_id` | TEXT | XGBoost | **User behavior** - Historical CTR per user (optional) | Behavioral |
| `session_id` | TEXT | XGBoost | **Session context** - Multi-query session patterns | Context |
| `conversation_id` | TEXT | XGBoost | **Conversational context** - Follow-up queries | Context |
| `query_text` | TEXT | BM25, XGBoost | **Primary input** - Text for BM25 tokenization, query analysis | Input |
| `decontextualized_query` | TEXT | BM25 | **Expanded query** - Better query representation for BM25 | Input |
| `site` | TEXT | XGBoost | **Domain feature** - Different sites may have different patterns | Context |
| `mode` | TEXT | XGBoost | **Query intent** - list/generate/summarize affects relevance | Context |
| `model` | TEXT | - | Metadata - LLM model used | Meta |
| `latency_total_ms` | REAL | - | Monitoring - System performance | Meta |
| `latency_retrieval_ms` | REAL | - | Monitoring - Retrieval speed | Meta |
| `latency_ranking_ms` | REAL | - | Monitoring - Ranking speed | Meta |
| `latency_generation_ms` | REAL | - | Monitoring - Generation speed | Meta |
| `num_results_retrieved` | INTEGER | XGBoost | **Result set size** - Affects ranking difficulty | Context |
| `num_results_ranked` | INTEGER | XGBoost | **Result set size** - Affects ranking difficulty | Context |
| `num_results_returned` | INTEGER | XGBoost | **Result set size** - Affects position importance | Context |
| `cost_usd` | REAL | - | Monitoring - Cost tracking | Meta |
| `error_occurred` | INTEGER | - | **Label filtering** - Exclude error queries from training | Filter |
| `error_message` | TEXT | - | Debugging - Error analysis | Meta |

### New Fields (Schema v2)

| Field | Data Type | ML Model | Training Purpose | Feature Type |
|-------|-----------|----------|------------------|--------------|
| `query_length_words` | INTEGER | XGBoost | **Query complexity** - Longer queries may need different ranking | Query Feature |
| `query_length_chars` | INTEGER | XGBoost | **Query complexity** - Alternative length metric | Query Feature |
| `has_temporal_indicator` | INTEGER | XGBoost | **Temporal intent** - "recent", "latest" suggests recency importance | Query Feature |
| `embedding_model` | TEXT | - | Metadata - Track which embeddings were used | Meta |
| `schema_version` | INTEGER | - | **Version control** - Track feature set evolution | Meta |

---

## Table 2: `retrieved_documents` - Retrieval Phase Results

### Existing Fields (Schema v1)

| Field | Data Type | ML Model | Training Purpose | Feature Type |
|-------|-----------|----------|------------------|--------------|
| `id` | INTEGER | - | Primary key | Key |
| `query_id` | TEXT | All | **Joins to queries** - Links features across tables | Key |
| `doc_url` | TEXT | XGBoost | **Document identifier** - Historical CTR per URL | Key |
| `doc_title` | TEXT | BM25, XGBoost | **Text matching** - BM25 scoring, title analysis | Input |
| `doc_description` | TEXT | BM25, XGBoost | **Text matching** - BM25 scoring, description analysis | Input |
| `doc_published_date` | TEXT | XGBoost | **Recency** - Calculate days since publication | Doc Feature |
| `doc_author` | TEXT | XGBoost | **Authority** - Has author = higher quality signal | Doc Feature |
| `doc_source` | TEXT | - | Metadata - Always 'qdrant_hybrid_search' currently | Meta |
| `retrieval_position` | INTEGER | XGBoost | **Initial ranking** - Position before re-ranking (strong signal) | Ranking Feature |
| `vector_similarity_score` | REAL | XGBoost | **Semantic relevance** - Core retrieval score | Retrieval Feature |
| `keyword_boost_score` | REAL | XGBoost | **Keyword match** - Legacy boosting score | Retrieval Feature |
| `bm25_score` | REAL | XGBoost | **BM25 score** - NEW: Will replace keyword_boost (Week 1-2) | Retrieval Feature |
| `temporal_boost` | REAL | XGBoost | **Recency boost** - How much recency affected score | Retrieval Feature |
| `domain_match` | INTEGER | XGBoost | **Domain relevance** - Domain-specific match | Query-Doc Feature |
| `final_retrieval_score` | REAL | XGBoost | **Combined score** - Final retrieval score (may be noisy) | Retrieval Feature |

### New Fields (Schema v2)

| Field | Data Type | ML Model | Training Purpose | Feature Type |
|-------|-----------|----------|------------------|--------------|
| `query_term_count` | INTEGER | BM25, XGBoost | **Query complexity** - Number of terms for BM25 | Query Feature |
| `doc_length` | INTEGER | BM25, XGBoost | **Document length** - BM25 normalization, quality signal | Doc Feature |
| `title_exact_match` | INTEGER | XGBoost | **Strong relevance** - Exact match in title = high relevance | Query-Doc Feature |
| `desc_exact_match` | INTEGER | XGBoost | **Strong relevance** - Exact match in description | Query-Doc Feature |
| `keyword_overlap_ratio` | REAL | XGBoost | **Keyword coverage** - % of query terms in document | Query-Doc Feature |
| `recency_days` | INTEGER | XGBoost | **Freshness** - Days since publication (normalized) | Doc Feature |
| `has_author` | INTEGER | XGBoost | **Quality signal** - Documents with authors = higher quality | Doc Feature |
| `retrieval_algorithm` | TEXT | XGBoost | **Algorithm tracking** - Which retrieval method (may affect scores) | Meta/Context |
| `schema_version` | INTEGER | - | **Version control** - Track feature set evolution | Meta |

---

## Table 3: `ranking_scores` - Ranking Phase Results

### Existing Fields (Schema v1)

| Field | Data Type | ML Model | Training Purpose | Feature Type |
|-------|-----------|----------|------------------|--------------|
| `id` | INTEGER | - | Primary key | Key |
| `query_id` | TEXT | All | **Joins to queries** | Key |
| `doc_url` | TEXT | XGBoost | **Document identifier** | Key |
| `ranking_position` | INTEGER | XGBoost | **Final position** - Critical feature for learning-to-rank | **LABEL** (position) |
| `llm_relevance_score` | REAL | XGBoost | **LLM judgment** - Semantic relevance from LLM | Ranking Feature |
| `llm_keyword_score` | REAL | XGBoost | **LLM keyword** - LLM's keyword matching assessment | Ranking Feature |
| `llm_semantic_score` | REAL | XGBoost | **LLM semantic** - Pure semantic relevance | Ranking Feature |
| `llm_freshness_score` | REAL | XGBoost | **LLM freshness** - LLM's temporal assessment | Ranking Feature |
| `llm_authority_score` | REAL | XGBoost | **LLM authority** - Source quality assessment | Ranking Feature |
| `llm_final_score` | REAL | XGBoost | **LLM overall** - Combined LLM score (strong signal) | Ranking Feature |
| `llm_snippet` | TEXT | - | Display - Generated description for UI | Meta |
| `xgboost_score` | REAL | - | **XGBoost prediction** - NEW: Will be filled by XGBoost model (Week 7-8) | Prediction |
| `xgboost_confidence` | REAL | - | **Prediction confidence** - NEW: Confidence for cascading logic | Prediction |
| `mmr_diversity_score` | REAL | XGBoost | **Diversity score** - NEW: MMR algorithm output (Week 1-2) | Ranking Feature |
| `final_ranking_score` | REAL | XGBoost | **Combined final** - May combine XGBoost + LLM | Ranking Feature |
| `ranking_method` | TEXT | XGBoost | **Method context** - 'llm_fast_track' vs 'llm_regular' | Context |

### New Fields (Schema v2)

| Field | Data Type | ML Model | Training Purpose | Feature Type |
|-------|-----------|----------|------------------|--------------|
| `relative_score` | REAL | XGBoost | **Normalized score** - Score relative to top result (0-1) | Ranking Feature |
| `score_percentile` | REAL | XGBoost | **Score distribution** - Percentile in result set (0-100) | Ranking Feature |
| `schema_version` | INTEGER | - | **Version control** | Meta |

---

## Table 4: `user_interactions` - User Engagement (LABELS)

### Existing Fields (Schema v1)

| Field | Data Type | ML Model | Training Purpose | Feature Type |
|-------|-----------|----------|------------------|--------------|
| `id` | INTEGER | - | Primary key | Key |
| `query_id` | TEXT | All | **Joins to queries** | Key |
| `doc_url` | TEXT | XGBoost | **Document identifier** | Key |
| `interaction_type` | TEXT | - | Metadata - click/dwell/scroll | Meta |
| `interaction_timestamp` | REAL | XGBoost | **Time on page** - Calculate dwell time | Behavioral |
| `result_position` | INTEGER | XGBoost | **Position bias** - Adjust for position in results | Context |
| `dwell_time_ms` | REAL | XGBoost | **LABEL (engagement)** - Primary engagement signal | **LABEL** |
| `scroll_depth_percent` | REAL | XGBoost | **LABEL (engagement)** - Secondary engagement signal | **LABEL** |
| `clicked` | INTEGER | XGBoost | **LABEL (binary)** - Primary binary relevance label | **LABEL** |
| `client_user_agent` | TEXT | XGBoost | **Device context** - Mobile vs desktop affects CTR | Context |
| `client_ip_hash` | TEXT | - | Privacy - Anonymized location | Privacy |

### New Fields (Schema v2)

| Field | Data Type | ML Model | Training Purpose | Feature Type |
|-------|-----------|----------|------------------|--------------|
| `schema_version` | INTEGER | - | **Version control** | Meta |

---

## Table 5: `feature_vectors` - Comprehensive ML Features (NEW - Schema v2)

This table consolidates all features for XGBoost training. It's generated from the other 4 tables via JOIN queries.

### Query Features (5 features)

| Field | Data Type | Source Table | Training Purpose | Feature Category |
|-------|-----------|--------------|------------------|------------------|
| `query_length_words` | INTEGER | queries | Query complexity | Query |
| `query_length_chars` | INTEGER | queries | Query complexity (alternative) | Query |
| `query_type` | TEXT | queries (derived) | Intent classification: question/statement/navigational | Query |
| `has_temporal_indicator` | INTEGER | queries | Temporal intent detection | Query |
| `has_brand_mention` | INTEGER | queries (derived) | Brand/entity recognition | Query |

### Document Features (8 features)

| Field | Data Type | Source Table | Training Purpose | Feature Category |
|-------|-----------|--------------|------------------|------------------|
| `doc_length_words` | INTEGER | retrieved_documents | Document size | Document |
| `doc_length_chars` | INTEGER | retrieved_documents | Document size (alternative) | Document |
| `title_length` | INTEGER | retrieved_documents (derived) | Title quality | Document |
| `has_publication_date` | INTEGER | retrieved_documents | Metadata completeness | Document |
| `recency_days` | INTEGER | retrieved_documents | Freshness | Document |
| `has_author` | INTEGER | retrieved_documents | Authority signal | Document |
| `schema_completeness` | REAL | retrieved_documents (derived) | Metadata quality score (0-1) | Document |
| `domain_authority` | REAL | retrieved_documents (derived) | Source reputation (0-1) | Document |

### Query-Document Features (10 features)

| Field | Data Type | Source Table | Training Purpose | Feature Category |
|-------|-----------|--------------|------------------|------------------|
| `vector_similarity` | REAL | retrieved_documents | Semantic match | Query-Doc |
| `bm25_score` | REAL | retrieved_documents | Keyword relevance | Query-Doc |
| `title_exact_match` | INTEGER | retrieved_documents | Strong relevance signal | Query-Doc |
| `desc_exact_match` | INTEGER | retrieved_documents | Strong relevance signal | Query-Doc |
| `keyword_overlap_ratio` | REAL | retrieved_documents | Term coverage | Query-Doc |
| `query_term_coverage` | REAL | derived | % query terms in doc | Query-Doc |
| `temporal_relevance` | REAL | derived | Match between query time intent & doc date | Query-Doc |
| `domain_match` | INTEGER | retrieved_documents | Domain relevance | Query-Doc |
| `entity_match_count` | INTEGER | derived | Named entity matches | Query-Doc |
| `partial_match_count` | INTEGER | derived | Partial keyword matches | Query-Doc |

### Ranking Features (5 features)

| Field | Data Type | Source Table | Training Purpose | Feature Category |
|-------|-----------|--------------|------------------|------------------|
| `retrieval_position` | INTEGER | retrieved_documents | Initial ranking | Ranking |
| `ranking_position` | INTEGER | ranking_scores | Final ranking | Ranking |
| `llm_score` | REAL | ranking_scores | LLM judgment | Ranking |
| `relative_score_to_top` | REAL | ranking_scores | Normalized score | Ranking |
| `score_percentile` | REAL | ranking_scores | Score distribution | Ranking |

### Labels (3 labels)

| Field | Data Type | Source Table | Training Purpose | Label Type |
|-------|-----------|--------------|------------------|------------|
| `clicked` | INTEGER | user_interactions | **PRIMARY LABEL** - Binary classification | Binary Label |
| `dwell_time_ms` | REAL | user_interactions | **ENGAGEMENT LABEL** - Regression target | Continuous Label |
| `relevance_grade` | INTEGER | manual labeling | **GRADED LABEL** - 0-4 scale (future) | Ordinal Label |

### Metadata

| Field | Data Type | Purpose |
|-------|-----------|---------|
| `id` | INTEGER/SERIAL | Primary key |
| `query_id` | TEXT | Foreign key to queries |
| `doc_url` | TEXT | Document identifier |
| `schema_version` | INTEGER | Feature set version |
| `created_at` | REAL | Feature generation timestamp |

---

## ML Model Usage Summary

### BM25 Algorithm (Week 1-2)

**Input Fields**:
- `queries.query_text` - Tokenize into terms
- `queries.decontextualized_query` - Expanded query
- `retrieved_documents.doc_title` - Document text field 1
- `retrieved_documents.doc_description` - Document text field 2
- `retrieved_documents.query_term_count` - Query length
- `retrieved_documents.doc_length` - Document length for normalization

**Output Fields**:
- `retrieved_documents.bm25_score` - BM25 relevance score

**Training**: None - BM25 is an unsupervised algorithm

---

### MMR Algorithm (Week 1-2)

**Input Fields**:
- `retrieved_documents.vector_similarity_score` - Relevance scores
- Document embeddings (not stored, computed on-the-fly)
- `ranking_scores.ranking_position` - Initial ranking

**Output Fields**:
- `ranking_scores.mmr_diversity_score` - Diversity score

**Training**: None - MMR is an unsupervised algorithm with configurable λ

---

### XGBoost Ranking Model (Week 4-8)

**Input Features** (28 features total):
- **Query Features** (5): length_words, length_chars, type, has_temporal, has_brand
- **Document Features** (8): doc_length, title_length, recency_days, has_author, etc.
- **Query-Doc Features** (10): vector_sim, bm25, exact_matches, overlap_ratio, etc.
- **Ranking Features** (5): retrieval_pos, ranking_pos, llm_score, relative_score, percentile

**Labels** (choose one training strategy):
1. **Binary Classification**: `user_interactions.clicked` (0/1)
   - Predict probability of click
   - Use all query-document pairs (clicked + not clicked)

2. **Regression**: `user_interactions.dwell_time_ms`
   - Predict engagement time
   - Only use clicked documents (dwell_time > 0)

3. **Learning-to-Rank**: `ranking_scores.ranking_position`
   - Optimize ranking order
   - Use pairwise or listwise ranking loss

4. **Multi-task**: Combine clicked + dwell_time
   - Two output heads: classification + regression
   - More robust predictions

**Output Fields**:
- `ranking_scores.xgboost_score` - Model prediction (0-1 or 0-100)
- `ranking_scores.xgboost_confidence` - Prediction confidence

**Training Data Source**:
- Join all 4 tables by `query_id` and `doc_url`
- Generate features into `feature_vectors` table
- Split by query_id (70% train, 15% val, 15% test)

---

## Feature Engineering Pipeline (Week 4)

```
Step 1: Raw Data Collection (Automatic - ongoing)
  ↓ queries, retrieved_documents, ranking_scores, user_interactions

Step 2: Feature Extraction (Script: ml/feature_engineering.py)
  ↓ JOIN tables + calculate derived features

Step 3: Feature Vectors Table (Output)
  ↓ 28 features + 3 labels per query-document pair

Step 4: Training Dataset (Script: ml/prepare_training_data.py)
  ↓ Filter, clean, split, export CSV/parquet

Step 5: XGBoost Training (Script: ml/train_ranker.py)
  ↓ Hyperparameter tuning, cross-validation

Step 6: Model Deployment (Module: core/xgboost_ranker.py)
  ↓ Load model, real-time inference
```

---

## Data Quality Considerations

### Required Fields (cannot be NULL for training)
- ✅ `query_id`, `doc_url` - Identifiers
- ✅ `query_text` - BM25 input
- ✅ `vector_similarity_score` - Core feature
- ✅ `retrieval_position` - Position feature
- ✅ `ranking_position` - Position feature

### Optional Fields (can be NULL, use default)
- ⚠️ `bm25_score` - NULL until BM25 implemented (use 0.0)
- ⚠️ `mmr_diversity_score` - NULL until MMR implemented (use 0.0)
- ⚠️ `llm_final_score` - NULL if fast-track skipped (use retrieval score)
- ⚠️ `dwell_time_ms` - NULL if not clicked (use 0.0)
- ⚠️ `doc_published_date` - NULL if no date (use average recency)

### Label Distribution Requirements
- **Imbalanced labels**: Most docs not clicked (clicked rate ~5-10%)
- **Solution**: Use class weights or focal loss in XGBoost
- **Minimum data**: 10,000+ query-document pairs (1,000+ queries)
- **Click distribution**: Need both clicked (positive) and not-clicked (negative) examples

---

## Version Control Strategy

### Schema v1 (Current - until Week 4)
- 4 tables: queries, retrieved_documents, ranking_scores, user_interactions
- `bm25_score`, `mmr_diversity_score`, `xgboost_score` are NULL
- Sufficient for BM25/MMR algorithm implementation

### Schema v2 (Week 4 onwards)
- Added ML feature columns to existing tables
- New `feature_vectors` table for consolidated features
- `schema_version = 2` in all tables
- Enables XGBoost training

### Future Schema v3 (if needed)
- Additional features discovered during training
- New label types (e.g., satisfaction ratings)
- `schema_version = 3`

---

## Summary: Field → Model Mapping

| ML Model | Primary Input Fields | Output Fields | Training Type |
|----------|---------------------|---------------|---------------|
| **BM25** | query_text, doc_title, doc_description, doc_length | bm25_score | Unsupervised |
| **MMR** | vector_similarity, embeddings (runtime) | mmr_diversity_score | Unsupervised |
| **XGBoost** | 28 features from all tables | xgboost_score, xgboost_confidence | Supervised |

**Training Labels for XGBoost**:
- Primary: `clicked` (binary)
- Secondary: `dwell_time_ms` (regression)
- Future: `relevance_grade` (ordinal, 0-4)

**Feature Count**:
- Schema v1: 14 features available
- Schema v2: 28+ features available
- Target for XGBoost: 25-30 features (avoid overfitting)
