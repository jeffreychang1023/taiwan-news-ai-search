# Quick Start: Enable Analytics in 5 Steps

**Time Required:** ~20 minutes
**Difficulty:** Easy

---

## Step 1: Add Tracker Script (2 min)

**File:** `static/news-search-prototype.html`
**Location:** Just before line 1145 (before the main `<script>` tag)

**Add:**
```html
<!-- Analytics Tracker -->
<script src="/analytics-tracker-sse.js"></script>
```

---

## Step 2: Initialize Tracker (5 min)

**File:** `static/news-search-prototype.html`
**Location:** Inside `<script>` tag, right after line 1145

**Add this entire block:**
```javascript
// ==================== ANALYTICS INITIALIZATION ====================
const analyticsTracker = new AnalyticsTrackerSSE('/api/analytics/event');
let currentAnalyticsQueryId = null;

// Event delegation: Track all clicks on article links
document.addEventListener('click', (event) => {
    const link = event.target.closest('.btn-read-more, a[href]');
    if (!link) return;

    const newsCard = link.closest('.news-card');
    if (!newsCard) return;

    const url = link.href;
    const allCards = document.querySelectorAll('.news-card');
    const position = Array.from(allCards).indexOf(newsCard);

    if (currentAnalyticsQueryId && url) {
        analyticsTracker.trackClick(url, position);
    }
});

// MutationObserver: Auto-track article displays
const articleObserver = new MutationObserver((mutations) => {
    mutations.forEach(mutation => {
        mutation.addedNodes.forEach(node => {
            if (node.nodeType === 1 && node.classList && node.classList.contains('news-card')) {
                const link = node.querySelector('a[href]');
                if (link && currentAnalyticsQueryId) {
                    const allCards = document.querySelectorAll('.news-card');
                    const position = Array.from(allCards).indexOf(node);
                    const url = link.href;

                    analyticsTracker.trackResultDisplayed(url, position, {
                        title: node.querySelector('.news-title')?.textContent || ''
                    });

                    node.dataset.analyticsUrl = url;
                    node.dataset.analyticsPosition = position;
                    analyticsTracker.observeResult(node);
                }
            }
        });
    });
});

articleObserver.observe(document.getElementById('listView'), { childList: true, subtree: true });
articleObserver.observe(document.getElementById('timelineView'), { childList: true, subtree: true });

console.log('[Analytics] Tracker initialized');
// ==================== END ANALYTICS INITIALIZATION ====================
```

---

## Step 3: Track Query Starts (3 min)

**File:** `static/news-search-prototype.html`
**Location:** Inside `performSearch()` function, after line 1649

**Find this:**
```javascript
async function performSearch() {
    const query = searchInput.value.trim();
    if (!query) return;

    // Hide initial state
    initialState.style.display = 'none';
```

**Add after `if (!query) return;`:**
```javascript
    // Analytics: Start tracking query
    currentAnalyticsQueryId = `query_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
    analyticsTracker.startQuery(currentAnalyticsQueryId, query);
```

---

## Step 4: Track Chat Queries (2 min)

**File:** `static/news-search-prototype.html`
**Location:** Inside `performFreeConversation()` function, after line 1772

**Find this:**
```javascript
async function performFreeConversation(query) {
    // Add user message to chat
    addChatMessage('user', query);

    // Clear input
    searchInput.value = '';
```

**Add after `addChatMessage('user', query);`:**
```javascript
    // Analytics: Track chat query
    currentAnalyticsQueryId = `chat_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
    analyticsTracker.startQuery(currentAnalyticsQueryId, query);
```

---

## Step 5: Register Backend Routes (5 min)

**File:** Main webserver file (e.g., `code/python/webserver/server.py`)
**Location:** After app creation, before `app.run()` or similar

**Add:**
```python
from webserver.analytics_handler import register_analytics_routes

# Register analytics routes
register_analytics_routes(app, db_path="data/analytics/query_logs.db")
```

---

## Test It! (3 min)

1. **Start your backend server**

2. **Open browser console** (F12)

3. **Navigate to** `http://localhost:8000/news-search-prototype.html`

4. **Perform a search**
   - Console should show: `[Analytics] Tracking query: query_...`
   - Console should show: `[Analytics-SSE] Started tracking query`

5. **Click on a result**
   - Console should show: `[Analytics-SSE] Click tracked: ...`
   - Console should show: `[Analytics-SSE] Event sent: result_clicked`

6. **Check backend logs**
   - Should see: `Received analytics event: result_clicked`

7. **Open dashboard**
   - Go to: `http://localhost:8000/analytics-dashboard.html`
   - Should see query count increase
   - Should see clicked results in table

---

## Troubleshooting

### "analyticsTracker is not defined"
**Fix:** Make sure Step 1 is done (script tag added) and file exists at `/static/analytics-tracker-sse.js`

### No console messages
**Fix:** Check browser console for JavaScript errors. Make sure code was added in correct locations.

### Events not reaching backend
**Fix:**
1. Check Network tab for failed POST requests
2. Verify backend analytics routes are registered (Step 5)
3. Check backend logs for errors

### Dashboard shows no data
**Fix:**
1. Wait 5 seconds (events are batched)
2. Check if `/api/analytics/event` endpoint returns 200
3. Query database directly: `sqlite3 data/analytics/query_logs.db "SELECT * FROM user_interactions;"`

---

## Done! 🎉

You now have analytics tracking enabled. The system will automatically collect:
- ✅ Query texts and timestamps
- ✅ Result clicks and positions
- ✅ Dwell time on results
- ✅ Scroll depth

All data is stored in `data/analytics/query_logs.db` and ready for ML training!

---

## Next Steps

After collecting data for 1-2 weeks:
1. Export training data: `http://localhost:8000/api/analytics/export_training_data?days=14`
2. Proceed to **Track B: BM25 Integration**
3. Proceed to **Track C: MMR Diversity**
4. Proceed to **Track D: XGBoost Training**

---

## Full Documentation

- **Detailed Instructions:** `ANALYTICS_INTEGRATION_INSTRUCTIONS.md`
- **Changelog & Rollback:** `LOGGING_IMPLEMENTATION_CHANGELOG.md`
- **Complete Summary:** `ANALYTICS_IMPLEMENTATION_SUMMARY.md`
