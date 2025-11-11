# Analytics Integration Instructions for news-search-prototype.html

## Overview

This document provides step-by-step instructions to integrate analytics tracking into `news-search-prototype.html`.

---

## Files Needed

1. **Backend:** `analytics-tracker-sse.js` (already created in `/static/`)
2. **Frontend:** Modifications to `news-search-prototype.html`

---

## Step 1: Add Script Tag

**Location:** Just before the `<script>` tag that contains the main JavaScript code (around line 1145)

**Add:**
```html
<!-- Analytics Tracker -->
<script src="/analytics-tracker-sse.js"></script>
```

---

## Step 2: Initialize Tracker

**Location:** Inside the `<script>` tag, at the very beginning (after line 1145)

**Add:**
```javascript
// ==========================================
// ANALYTICS TRACKER INITIALIZATION
// ==========================================
const analyticsTracker = new AnalyticsTrackerSSE('/api/analytics/event');
let currentAnalyticsQueryId = null;

// Helper function to track article clicks
function setupArticleAnalytics(element, url, position) {
    if (!currentAnalyticsQueryId || !url) return;

    // Add data attributes
    element.dataset.analyticsUrl = url;
    element.dataset.analyticsPosition = position;

    // Track display
    analyticsTracker.trackResultDisplayed(url, position, {
        title: element.querySelector('.news-title')?.textContent || ''
    });

    // Set up click tracking
    const links = element.querySelectorAll('a[href]');
    links.forEach(link => {
        link.addEventListener('click', () => {
            analyticsTracker.trackClick(url, position);
        });
    });

    // Observe for visibility
    analyticsTracker.observeResult(element);
}

console.log('[Analytics] Tracker initialized');
// ==========================================
```

---

## Step 3: Track Query Start

**Location:** Inside `performSearch()` function, right after `if (!query) return;` (line ~1649)

**Find:**
```javascript
async function performSearch() {
    const query = searchInput.value.trim();
    if (!query) return;

    // Hide initial state
    initialState.style.display = 'none';
```

**Add After Line 1649:**
```javascript
    // Analytics: Start tracking query
    currentAnalyticsQueryId = `query_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
    analyticsTracker.startQuery(currentAnalyticsQueryId, query);
    console.log('[Analytics] Tracking query:', currentAnalyticsQueryId);
```

---

## Step 4: Track Article Rendering

**Location:** Inside `populateResultsFromAPI()` function, after rendering articles (line ~1562)

**Find (around line 1506-1562):**
```javascript
articles.forEach((article, index) => {
    const schema = article.schema_object || article;
    // ... lots of code ...

    listView.innerHTML += cardHTML;

    // Group by date for timeline view
    if (!articlesByDate[date]) {
```

**Replace `listView.innerHTML += cardHTML;` with:**
```javascript
    // Create card element instead of HTML string
    const cardElement = document.createElement('div');
    cardElement.innerHTML = cardHTML;
    const newsCard = cardElement.firstElementChild;
    listView.appendChild(newsCard);

    // Analytics: Track this article
    setupArticleAnalytics(newsCard, url, index);
```

---

## Step 5: Track Timeline View Articles

**Location:** Inside `populateResultsFromAPI()` function, timeline view rendering (line ~1577-1597)

**Find:**
```javascript
sortedDates.forEach(date => {
    const dateArticles = articlesByDate[date];
    const timelineHTML = `...`;

    timelineView.innerHTML += timelineHTML;
});
```

**Replace with:**
```javascript
sortedDates.forEach(date => {
    const dateArticles = articlesByDate[date];

    // Create timeline date container
    const timelineContainer = document.createElement('div');
    timelineContainer.className = 'timeline-date';

    const timelineDot = document.createElement('div');
    timelineDot.className = 'timeline-dot';
    timelineContainer.appendChild(timelineDot);

    const dateLabel = document.createElement('div');
    dateLabel.className = 'date-label';
    dateLabel.textContent = date;
    timelineContainer.appendChild(dateLabel);

    // Add each article
    dateArticles.forEach((art, idx) => {
        const articleCard = document.createElement('div');
        articleCard.className = 'news-card';
        articleCard.innerHTML = `
            <div class="news-title">${escapeHTML(art.title)}</div>
            <div class="news-meta">
                <span>🏢 ${escapeHTML(art.publisher)}</span>
                <div class="relevance">
                    <span class="stars">${art.starsHTML}</span>
                    <span>相關度 ${art.relevancePercent}%</span>
                </div>
            </div>
            ${art.description ? `<div class="news-excerpt">${escapeHTML(art.description)}</div>` : ''}
            <a href="${escapeHTML(art.url)}" class="btn-read-more" target="_blank">閱讀全文 →</a>
        `;
        timelineContainer.appendChild(articleCard);

        // Analytics: Track this article in timeline view
        setupArticleAnalytics(articleCard, art.url, idx);
    });

    timelineView.appendChild(timelineContainer);
});
```

---

## Step 6: Track Chat Mode Queries

**Location:** Inside `performFreeConversation()` function (line ~1770)

**Find:**
```javascript
async function performFreeConversation(query) {
    // Add user message to chat
    addChatMessage('user', query);

    // Clear input
    searchInput.value = '';
```

**Add After `addChatMessage('user', query);`:**
```javascript
    // Analytics: Track chat query
    currentAnalyticsQueryId = `chat_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
    analyticsTracker.startQuery(currentAnalyticsQueryId, query);
```

---

## Alternative: Simpler Approach Using Event Delegation

If the above modifications are too extensive, here's a simpler approach that doesn't require changing the rendering code:

**Add this after tracker initialization:**

```javascript
// Simple approach: Use event delegation to track clicks on any article link
document.addEventListener('click', (event) => {
    // Check if click is on article link
    const link = event.target.closest('.btn-read-more, a[href]');
    if (!link) return;

    // Find parent news card
    const newsCard = link.closest('.news-card');
    if (!newsCard) return;

    // Get article info
    const url = link.href;
    const titleElement = newsCard.querySelector('.news-title');
    const title = titleElement ? titleElement.textContent : '';

    // Get position (index of card)
    const allCards = document.querySelectorAll('.news-card');
    const position = Array.from(allCards).indexOf(newsCard);

    // Track click
    if (currentAnalyticsQueryId && url) {
        analyticsTracker.trackClick(url, position);
        console.log('[Analytics] Tracked click:', url);
    }
});

// Track article displays after results are rendered
const articleObserver = new MutationObserver((mutations) => {
    mutations.forEach(mutation => {
        mutation.addedNodes.forEach(node => {
            if (node.nodeType === 1 && node.classList && node.classList.contains('news-card')) {
                // New article card added
                const link = node.querySelector('a[href]');
                if (link && currentAnalyticsQueryId) {
                    const allCards = document.querySelectorAll('.news-card');
                    const position = Array.from(allCards).indexOf(node);
                    const url = link.href;

                    analyticsTracker.trackResultDisplayed(url, position, {
                        title: node.querySelector('.news-title')?.textContent || ''
                    });

                    // Set up visibility tracking
                    node.dataset.analyticsUrl = url;
                    node.dataset.analyticsPosition = position;
                    analyticsTracker.observeResult(node);
                }
            }
        });
    });
});

// Observe the list view and timeline view for new articles
articleObserver.observe(document.getElementById('listView'), { childList: true, subtree: true });
articleObserver.observe(document.getElementById('timelineView'), { childList: true, subtree: true });
```

---

## Testing

1. **Open Browser Console**
   - You should see: `[Analytics-SSE] Tracker initialized`

2. **Perform a Search**
   - Console should show: `[Analytics] Tracking query: query_...`
   - Console should show: `[Analytics-SSE] Started tracking query: ...`

3. **Click on a Result**
   - Console should show: `[Analytics-SSE] Click tracked: ...`
   - Console should show: `[Analytics-SSE] Event sent: result_clicked`

4. **Check Backend**
   - Backend logs should show: `Received analytics event: result_clicked`
   - Database should have entry in `user_interactions` table

5. **View Analytics Dashboard**
   - Open: `http://localhost:8000/analytics-dashboard.html`
   - Should see query count increase
   - Should see clicked results

---

## Troubleshooting

### No Analytics Messages in Console
- Check that `analytics-tracker-sse.js` is loaded (Network tab)
- Check for JavaScript errors in console
- Verify tracker is initialized before search

### Events Not Reaching Backend
- Check Network tab for `/api/analytics/event` requests
- Check for CORS errors
- Verify backend analytics routes are registered
- Check backend logs for errors

### Clicks Not Being Tracked
- Verify `currentAnalyticsQueryId` is set
- Check that links have correct href attributes
- Check event delegation setup

---

## Recommended Approach

**Use the "Alternative: Simpler Approach" method** as it:
- Requires minimal code changes
- Uses event delegation (more robust)
- Uses MutationObserver (automatic detection)
- Less likely to break existing code

The simpler approach can be added in a single block of code right after tracker initialization, making it easy to test and roll back if needed.

---

## Rollback

To remove analytics tracking:
1. Remove the `<script src="/analytics-tracker-sse.js"></script>` tag
2. Remove all code added in Step 2 (initialization)
3. Remove all code added in Steps 3-6 (tracking calls)

Or if using the simpler approach:
1. Remove the `<script src="/analytics-tracker-sse.js"></script>` tag
2. Remove the initialization and event delegation code block

---

## Next Steps

After integration:
1. Test thoroughly with browser console open
2. Verify events in database: `SELECT * FROM user_interactions LIMIT 10;`
3. Check analytics dashboard for live data
4. Proceed with backend logging integration (baseHandler, ranking, etc.)

