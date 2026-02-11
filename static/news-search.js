        const searchInput = document.getElementById('searchInput');
        const btnSearch = document.getElementById('btnSearch');
        const initialState = document.getElementById('initialState');
        const loadingState = document.getElementById('loadingState');
        const resultsSection = document.getElementById('resultsSection');
        const listView = document.getElementById('listView');
        const timelineView = document.getElementById('timelineView');
        const btnShare = document.getElementById('btnShareSidebar');
        const modalOverlay = document.getElementById('modalOverlay');
        const btnCloseModal = document.getElementById('btnCloseModal');
        const summaryToggle = document.getElementById('summaryToggle');
        const btnToggleSummary = document.getElementById('btnToggleSummary');
        const summaryLoading = document.getElementById('summaryLoading');
        const modeToggle = document.getElementById('modeToggle');
        const modeButtons = document.querySelectorAll('.mode-button');
        const chatContainer = document.getElementById('chatContainer');
        const chatMessagesEl = document.getElementById('chatMessages');
        const searchContainer = document.getElementById('searchContainer');
        const chatInputContainer = document.getElementById('chatInputContainer');
        const chatLoading = document.getElementById('chatLoading');

        let summaryExpanded = false;
        let summaryGenerated = false;

        // Conversation history tracking
        let conversationHistory = [];

        // Store complete session data for each query (query, answer, articles)
        let sessionHistory = [];

        // Store all saved sessions (when user clicks "新對話")
        // Load from localStorage on startup
        let savedSessions = [];
        try {
            const stored = localStorage.getItem('taiwanNewsSavedSessions');
            if (stored) {
                savedSessions = JSON.parse(stored);
                console.log(`Loaded ${savedSessions.length} saved sessions from localStorage`);
            }
        } catch (e) {
            console.error('Failed to load saved sessions from localStorage:', e);
        }

        // Track the current loaded session ID to prevent duplicate saves
        let currentLoadedSessionId = null;

        // Mode tracking: 'search', 'deep_research', or 'chat'
        let currentMode = 'search';

        // User Knowledge Base - temporary user_id (will be replaced with OAuth)
        const TEMP_USER_ID = 'demo_user_001';
        let userFiles = [];
        let includePrivateSources = true; // Default to true

        // Site Filter - list of available sites and selected sites
        let availableSites = [];
        let selectedSites = []; // Empty means "all"

        // ==================== ANALYTICS INITIALIZATION ====================
        const analyticsTracker = new AnalyticsTrackerSSE('/api/analytics/event');
        let currentAnalyticsQueryId = null;

        // Track current conversation ID for multi-turn conversations
        let currentConversationId = null;

        // Search cancellation mechanism — prevents stale search results from corrupting UI
        let searchGenerationId = 0;
        let currentSearchAbortController = null;
        let currentSearchEventSource = null;

        // Bug #23: Deep Research & Free Conversation abort infrastructure
        let currentDeepResearchEventSource = null;
        let currentFreeConvAbortController = null;

        // Session ID for analytics and A/B testing (persists until browser tab closes)
        let currentSessionId = sessionStorage.getItem('nlweb_session_id');
        if (!currentSessionId) {
            currentSessionId = 'sess_' + crypto.randomUUID().replace(/-/g, '').substring(0, 12);
            sessionStorage.setItem('nlweb_session_id', currentSessionId);
            console.log('[Session] Generated new session_id:', currentSessionId);
        } else {
            console.log('[Session] Using existing session_id:', currentSessionId);
        }

        // Event delegation: Track all clicks on article links (left, middle, right)
        const handleLinkClick = (event) => {
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
        };

        // Listen for all types of clicks
        document.addEventListener('click', handleLinkClick);        // Left click
        document.addEventListener('auxclick', handleLinkClick);     // Middle click
        document.addEventListener('contextmenu', handleLinkClick);  // Right click

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

        // Chat history for free conversation mode
        let chatHistory = [];

        // Pinned messages (Line-style announcement)
        let pinnedMessages = [];
        let messageIdCounter = 0;
        const MAX_PINNED_MESSAGES = 5;

        // Pinned news cards
        let pinnedNewsCards = [];
        const MAX_PINNED_NEWS = 10;

        // Accumulated articles from ALL searches in this conversation
        let accumulatedArticles = [];

        // Store Deep Research report for free conversation follow-up
        let currentResearchReport = null;

        // Store reasoning chain data for sharing/verification
        let currentArgumentGraph = null;
        let currentChainAnalysis = null;
        let shareContentOverride = null;  // When non-null, share modal uses this content instead

        // ==================== 新版模式切換與 Popup 邏輯 ====================

        // 新版模式按鈕（搜尋框內）
        const modeButtonsInline = document.querySelectorAll('.mode-btn-inline');
        const advancedSearchPopup = document.getElementById('advancedSearchPopup');
        const popupOverlay = document.getElementById('popupOverlay');
        const popupClose = document.getElementById('popupClose');
        const btnUploadInline = document.getElementById('btnUploadInline');

        // Research Mode（radio group）
        const researchRadioItems = document.querySelectorAll('.research-radio-item');
        let currentResearchMode = 'discovery'; // Default mode

        // 追蹤使用者是否已確認進階搜尋設定（點擊過 popup 內的選項）
        let advancedSearchConfirmed = false;

        // 更新上傳按鈕可見性
        function updateUploadButtonVisibility() {
            if (currentMode === 'deep_research' || currentMode === 'chat') {
                btnUploadInline.classList.add('visible');
            } else {
                btnUploadInline.classList.remove('visible');
            }
        }

        // 顯示/隱藏 popup
        function showAdvancedPopup() {
            advancedSearchPopup.classList.add('visible');
            popupOverlay.classList.add('visible');
        }

        function hideAdvancedPopup() {
            advancedSearchPopup.classList.remove('visible');
            popupOverlay.classList.remove('visible');
            // 關閉 popup 時標記已確認（因為一定有預設值 discovery）
            advancedSearchConfirmed = true;
        }

        // 點擊 popup 外部關閉
        popupOverlay.addEventListener('click', hideAdvancedPopup);
        popupClose.addEventListener('click', hideAdvancedPopup);

        // 新版模式切換處理
        modeButtonsInline.forEach(button => {
            button.addEventListener('click', () => {
                const newMode = button.dataset.mode;

                // 如果點擊進階搜尋且已經是進階搜尋模式，toggle popup
                if (newMode === 'deep_research' && currentMode === 'deep_research') {
                    if (advancedSearchPopup.classList.contains('visible')) {
                        hideAdvancedPopup();
                    } else {
                        showAdvancedPopup();
                    }
                    return;
                }

                // Don't do anything if clicking the current mode (except deep_research)
                if (newMode === currentMode) return;

                // Update button states (新版)
                modeButtonsInline.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');

                // 同步舊版按鈕狀態（保持 JS 相容）
                modeButtons.forEach(btn => {
                    btn.classList.remove('active');
                    if (btn.dataset.mode === newMode) {
                        btn.classList.add('active');
                    }
                });

                // Update current mode
                const previousMode = currentMode;
                currentMode = newMode;

                // Handle mode-specific UI changes
                if (newMode === 'search') {
                    btnSearch.textContent = '搜尋';
                    searchInput.placeholder = '問我任何新聞相關問題，例如：最近台灣資安政策有什麼進展？';

                    // Move search container back to original position if coming from chat/deep_research
                    if (previousMode === 'chat' || previousMode === 'deep_research') {
                        const mainContainer = document.querySelector('main .container');
                        const loadingStateEl = document.getElementById('loadingState');
                        mainContainer.insertBefore(searchContainer, loadingStateEl);
                        chatInputContainer.style.display = 'none';
                        chatContainer.classList.remove('active');
                    }

                    hideAdvancedPopup();
                } else if (newMode === 'deep_research') {
                    btnSearch.textContent = '搜尋';
                    searchInput.placeholder = '輸入問題進行深度研究分析...';

                    // Move search container to chat area bottom
                    chatContainer.classList.add('active');
                    chatInputContainer.appendChild(searchContainer);
                    chatInputContainer.style.display = 'block';

                    // 自動顯示 popup 並重置確認狀態
                    advancedSearchConfirmed = false;
                    showAdvancedPopup();
                } else if (newMode === 'chat') {
                    btnSearch.textContent = '發送';
                    searchInput.placeholder = '研究助理會參考摘要內容及您釘選的文章來回答...';

                    // chatContainer 已獨立於 resultsSection，不需要顯示 resultsSection
                    chatContainer.classList.add('active');
                    chatInputContainer.appendChild(searchContainer);
                    chatInputContainer.style.display = 'block';

                    hideAdvancedPopup();
                }

                // 更新上傳按鈕可見性
                updateUploadButtonVisibility();

            });
        });

        // Research Radio Items 處理
        researchRadioItems.forEach(item => {
            item.addEventListener('click', () => {
                // Update active states
                researchRadioItems.forEach(i => i.classList.remove('active'));
                item.classList.add('active');

                // Check the radio button
                const radio = item.querySelector('input[type="radio"]');
                if (radio) radio.checked = true;

                // Update current research mode
                currentResearchMode = item.dataset.researchMode;
                console.log('[Research Mode] Selected:', currentResearchMode);

                // 標記已確認設定
                advancedSearchConfirmed = true;
            });
        });

        // 進階設定 checkbox 也標記已確認
        const kgToggleCheckbox = document.getElementById('kgToggle');
        const webSearchToggleCheckbox = document.getElementById('webSearchToggle');

        kgToggleCheckbox.addEventListener('change', () => {
            advancedSearchConfirmed = true;
        });

        webSearchToggleCheckbox.addEventListener('change', () => {
            advancedSearchConfirmed = true;
        });

        // 初始化上傳按鈕可見性
        updateUploadButtonVisibility();

        // ==================== 左側邊欄系統 ====================
        const leftSidebar = document.getElementById('leftSidebar');
        const btnExpandSidebar = document.getElementById('btnExpandSidebar');
        const btnCollapseSidebar = document.getElementById('btnCollapseSidebar');
        const btnNewConversation = document.getElementById('btnNewConversation');
        const btnToggleCategories = document.getElementById('btnToggleCategories');
        // History Popup 元素
        const btnHistorySearch = document.getElementById('btnHistorySearch');
        const historyPopupOverlay = document.getElementById('historyPopupOverlay');
        const historyPopupClose = document.getElementById('historyPopupClose');
        const historyPopupSearchInput = document.getElementById('historyPopupSearchInput');
        const historyPopupList = document.getElementById('historyPopupList');
        const btnSettings = document.getElementById('btnSettings');

        // 展開按鈕：開啟側邊欄
        btnExpandSidebar.addEventListener('click', () => {
            leftSidebar.classList.add('visible');
            btnExpandSidebar.classList.add('hidden');
        });

        // 收回按鈕：關閉側邊欄
        btnCollapseSidebar.addEventListener('click', () => {
            leftSidebar.classList.remove('visible');
            btnExpandSidebar.classList.remove('hidden');
        });

        // 新對話按鈕：儲存當前對話後清空
        btnNewConversation.addEventListener('click', () => {
            // 如果有內容，先儲存
            if (sessionHistory.length > 0) {
                saveCurrentSession();
            }
            // 清空並重置
            resetConversation();
            // 關閉側邊欄並顯示展開按鈕
            leftSidebar.classList.remove('visible');
            btnExpandSidebar.classList.remove('hidden');
        });

        // 開啟資料夾 (btnToggleCategories) - 行為在 FOLDER/PROJECT SYSTEM 區段定義

        // 說明與設置（placeholder）
        btnSettings.addEventListener('click', () => {
            alert('說明與設置功能即將推出！');
        });

        // ==================== 歷史搜尋 Popup ====================

        // 顯示 popup
        function showHistoryPopup() {
            historyPopupOverlay.classList.add('visible');
            historyPopupSearchInput.value = '';
            historyPopupSearchInput.focus();
            renderHistoryPopup();
        }

        // 隱藏 popup
        function hideHistoryPopup() {
            historyPopupOverlay.classList.remove('visible');
        }

        // 點擊「歷史搜尋」按鈕
        btnHistorySearch.addEventListener('click', showHistoryPopup);

        // 點擊關閉按鈕
        historyPopupClose.addEventListener('click', hideHistoryPopup);

        // 點擊 overlay 關閉
        historyPopupOverlay.addEventListener('click', (e) => {
            if (e.target === historyPopupOverlay) {
                hideHistoryPopup();
            }
        });

        // ESC 鍵關閉
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && historyPopupOverlay.classList.contains('visible')) {
                hideHistoryPopup();
            }
        });

        // 搜尋框輸入時過濾
        historyPopupSearchInput.addEventListener('input', () => {
            renderHistoryPopup(historyPopupSearchInput.value.trim().toLowerCase());
        });

        // 渲染 popup 歷史記錄列表
        function renderHistoryPopup(filterText = '') {
            historyPopupList.innerHTML = '';

            if (savedSessions.length === 0) {
                historyPopupList.innerHTML = '<div class="history-popup-empty">尚無搜尋記錄</div>';
                return;
            }

            // 過濾
            let filteredSessions = savedSessions.slice().reverse();
            if (filterText) {
                filteredSessions = filteredSessions.filter(session =>
                    session.title.toLowerCase().includes(filterText)
                );
            }

            if (filteredSessions.length === 0) {
                historyPopupList.innerHTML = '<div class="history-popup-empty">找不到符合的記錄</div>';
                return;
            }

            filteredSessions.forEach(session => {
                const date = new Date(session.createdAt);
                const dateStr = date.toLocaleDateString('zh-TW', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit'
                });

                const item = document.createElement('div');
                item.className = 'history-popup-item';
                item.innerHTML = `
                    <div class="history-popup-item-content">
                        <div class="history-popup-item-title">${escapeHTML(session.title)}</div>
                        <div class="history-popup-item-date">${dateStr}</div>
                    </div>
                    <span class="history-popup-item-icon">→</span>
                `;

                item.addEventListener('click', () => {
                    // 切換前先保存當前對話（防止深度報告等狀態丟失）
                    if (sessionHistory.length > 0 || currentResearchReport) {
                        saveCurrentSession();
                    }
                    loadSavedSession(session);
                    hideHistoryPopup();
                    // 關閉左側邊欄
                    leftSidebar.classList.remove('visible');
                    btnExpandSidebar.classList.remove('hidden');
                });

                historyPopupList.appendChild(item);
            });
        }

        // 儲存當前對話
        function saveCurrentSession() {
            const existingSessionIndex = currentLoadedSessionId !== null
                ? savedSessions.findIndex(s => s.id === currentLoadedSessionId)
                : -1;

            // Prepare research report data with reasoning chain
            const researchReportData = currentResearchReport ? {
                ...currentResearchReport,
                argumentGraph: currentArgumentGraph ? [...currentArgumentGraph] : null,
                chainAnalysis: currentChainAnalysis ? { ...currentChainAnalysis } : null
            } : null;

            if (existingSessionIndex !== -1) {
                // 更新現有 session
                savedSessions[existingSessionIndex] = {
                    id: currentLoadedSessionId,
                    title: conversationHistory[0] || '未命名搜尋',
                    conversationHistory: [...conversationHistory],
                    sessionHistory: [...sessionHistory],
                    chatHistory: [...chatHistory],
                    accumulatedArticles: [...accumulatedArticles],
                    pinnedMessages: [...pinnedMessages],
                    pinnedNewsCards: [...pinnedNewsCards],
                    researchReport: researchReportData,
                    createdAt: savedSessions[existingSessionIndex].createdAt,
                    updatedAt: Date.now()
                };
            } else {
                // 新增 session
                const newSession = {
                    id: Date.now(),
                    title: conversationHistory[0] || '未命名搜尋',
                    conversationHistory: [...conversationHistory],
                    sessionHistory: [...sessionHistory],
                    chatHistory: [...chatHistory],
                    accumulatedArticles: [...accumulatedArticles],
                    pinnedMessages: [...pinnedMessages],
                    pinnedNewsCards: [...pinnedNewsCards],
                    researchReport: researchReportData,
                    createdAt: Date.now()
                };
                savedSessions.push(newSession);
                currentLoadedSessionId = newSession.id;
            }

            // 儲存到 localStorage
            localStorage.setItem('taiwanNewsSavedSessions', JSON.stringify(savedSessions));
            console.log('Session saved');

            document.dispatchEvent(new CustomEvent('session-saved'));
        }

        // 重置對話
        // ===== 共用 UI 重置函式 =====
        // 將搜尋框歸位、隱藏聊天/資料夾、重置模式按鈕、清空結果區
        function resetToHome() {
            // 搬回 searchContainer
            if (searchContainer.parentElement === chatInputContainer) {
                const mainContainer = document.querySelector('main .container');
                const loadingStateEl = document.getElementById('loadingState');
                mainContainer.insertBefore(searchContainer, loadingStateEl);
            }
            searchContainer.style.display = 'block';
            chatInputContainer.style.display = 'none';
            // 清除 inline style，讓 CSS .chat-container { display: none } 生效
            // 不能用 style.display = 'none'，否則之後 .active class 無法覆蓋 inline style
            chatContainer.style.display = '';
            chatContainer.classList.remove('active');
            chatMessagesEl.innerHTML = '';

            // 關閉資料夾頁
            const folderPageEl = document.getElementById('folderPage');
            if (folderPageEl) folderPageEl.style.display = 'none';
            _preFolderState = null;

            // 重置模式為 search（兩套按鈕同步）
            currentMode = 'search';
            btnSearch.textContent = '搜尋';
            searchInput.placeholder = '問我任何新聞相關問題，例如：最近台灣資安政策有什麼進展？';
            modeButtons.forEach(btn => btn.classList.remove('active'));
            if (modeButtons[0]) modeButtons[0].classList.add('active');
            modeButtonsInline.forEach(btn => btn.classList.remove('active'));
            const searchInlineBtn = document.querySelector('.mode-btn-inline[data-mode="search"]');
            if (searchInlineBtn) searchInlineBtn.classList.add('active');

            // 重置結果區
            resultsSection.classList.remove('active');
            resultsSection.style.display = '';
            listView.innerHTML = '';
            timelineView.innerHTML = '';

            // 隱藏釘選 banner
            const pinnedBanner = document.getElementById('pinnedBanner');
            if (pinnedBanner) pinnedBanner.style.display = 'none';

            // 重置釘選新聞列表
            const pinnedNewsList = document.getElementById('pinnedNewsList');
            if (pinnedNewsList) {
                pinnedNewsList.innerHTML = '<div class="pinned-news-empty">尚未釘選任何新聞</div>';
            }
        }

        function resetConversation() {
            cancelActiveSearch();

            // 清空所有資料
            conversationHistory = [];
            sessionHistory = [];
            chatHistory = [];
            accumulatedArticles = [];
            pinnedMessages = [];
            pinnedNewsCards = [];
            currentLoadedSessionId = null;
            currentResearchReport = null;
            currentConversationId = null;

            // 共用 UI 重置
            resetToHome();

            // resetConversation 專有的重置
            searchInput.value = '';
            initialState.style.display = 'block';

            // 清空右側 Tab「搜尋紀錄」（conversationHistory 已被清空）
            renderConversationHistory();

            // 重置 AI 摘要
            const summaryContent = document.getElementById('summaryContent');
            if (summaryContent) {
                summaryContent.innerHTML = '';
            }
            summaryGenerated = false;

            console.log('Conversation reset');
        }

        // ==================== 右側 Tab 面板系統 ====================
        const rightTabLabels = document.querySelectorAll('.right-tab-label');
        const rightTabPanels = document.querySelectorAll('.right-tab-panel');
        const rightTabCloseButtons = document.querySelectorAll('.right-tab-panel-close');
        let currentOpenTab = null;

        // Tab 標籤點擊處理
        rightTabLabels.forEach(label => {
            label.addEventListener('click', () => {
                const tabName = label.dataset.tab;

                // 如果點擊的是當前開啟的 Tab，則關閉
                if (currentOpenTab === tabName) {
                    closeAllTabs();
                    return;
                }

                // 關閉其他 Tab，開啟此 Tab
                closeAllTabs();
                openTab(tabName);
            });
        });

        // 關閉按鈕處理
        rightTabCloseButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                closeAllTabs();
            });
        });

        function openTab(tabName) {
            const label = document.querySelector(`.right-tab-label[data-tab="${tabName}"]`);
            const panel = document.querySelector(`.right-tab-panel[data-tab="${tabName}"]`);

            if (label && panel) {
                label.classList.add('active');
                panel.classList.add('visible');
                currentOpenTab = tabName;

                // 如果是搜尋紀錄 Tab，重新載入當前 session 的查詢列表
                if (tabName === 'history') {
                    renderConversationHistory();
                }
            }
        }

        function closeAllTabs() {
            rightTabLabels.forEach(l => l.classList.remove('active'));
            rightTabPanels.forEach(p => p.classList.remove('visible'));
            currentOpenTab = null;
        }

        // ==================== 舊版模式切換（保留供相容） ====================
        // Mode Toggle handler - Handle three modes (legacy, kept for JS compatibility)
        modeButtons.forEach(button => {
            button.addEventListener('click', () => {
                const newMode = button.dataset.mode;
                if (newMode === currentMode) return;

                // 同步觸發新版按鈕
                const inlineBtn = document.querySelector(`.mode-btn-inline[data-mode="${newMode}"]`);
                if (inlineBtn) inlineBtn.click();
            });
        });

        // Function to render conversation history
        // 渲染當前 session 的查詢歷史到右側 Tab「搜尋紀錄」
        function renderConversationHistory() {
            const container = document.getElementById('savedSessionsListNew');
            if (!container) return;

            if (conversationHistory.length === 0) {
                container.innerHTML = '<div class="empty-sessions">尚無查詢紀錄</div>';
                return;
            }

            container.innerHTML = '';

            conversationHistory.forEach((query, index) => {
                const item = document.createElement('div');
                item.className = 'saved-session-item';
                item.innerHTML = `
                    <div class="saved-session-item-title">${index + 1}. ${escapeHTML(query)}</div>
                `;

                // 點擊回溯到該次查詢的結果
                item.addEventListener('click', () => {
                    restoreSession(index);
                    closeAllTabs();
                });

                container.appendChild(item);
            });
        }

        // Function to restore a previous session
        function restoreSession(sessionIndex) {
            if (sessionIndex >= 0 && sessionIndex < sessionHistory.length) {
                const session = sessionHistory[sessionIndex];
                console.log('Restoring session:', session);

                // Populate UI with the stored session data
                populateResultsFromAPI(session.data, session.query);

                // Show results section
                resultsSection.classList.add('active');

                // Scroll to results
                resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }

        // Function to handle streaming SSE requests
        async function handleStreamingRequest(url, query) {
            return new Promise((resolve, reject) => {
                const eventSource = new EventSource(url);
                currentSearchEventSource = eventSource; // Store for cancellation
                let accumulatedData = {};
                let memoryNotifications = [];

                eventSource.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        console.log('SSE message received:', data);

                        // Handle different message types
                        switch(data.message_type) {
                            case 'begin-nlweb-response':
                                // Query started - capture query_id and conversation_id
                                if (data.query_id) {
                                    currentAnalyticsQueryId = data.query_id;
                                    analyticsTracker.startQuery(currentAnalyticsQueryId, data.query);
                                    console.log('[Analytics] Using backend query_id:', currentAnalyticsQueryId);
                                }
                                if (data.conversation_id) {
                                    currentConversationId = data.conversation_id;
                                    console.log('[Conversation] Using backend conversation_id:', currentConversationId);
                                }
                                break;

                            case 'remember':
                                // Memory request detected!
                                if (data.item_to_remember) {
                                    showMemoryNotification(data.item_to_remember);
                                    memoryNotifications.push(data.item_to_remember);
                                }
                                break;

                            case 'intermediate_result':
                                // Deep Research progress update
                                updateReasoningProgress(data);
                                break;

                            case 'clarification_required':
                                // Clarification for regular search (not yet implemented in-chat)
                                console.warn('[Clarification] Received clarification_required in regular search — not handled');
                                break;

                            case 'time_filter_relaxed':
                                // Time filter was too strict — show warning banner
                                console.warn('[Temporal] Time filter relaxed:', data.content);
                                showTimeFilterRelaxedWarning(data.content);
                                break;

                            case 'complete':
                                // Stream complete, close connection
                                console.log('Stream complete. Accumulated data:', accumulatedData);
                                eventSource.close();
                                currentSearchEventSource = null;
                                resolve(accumulatedData);
                                break;

                            default:
                                // Accumulate other data (nlws, etc.)
                                console.log('Accumulating data:', data);
                                Object.assign(accumulatedData, data);
                                console.log('Accumulated so far:', accumulatedData);
                                break;
                        }
                    } catch (e) {
                        console.error('Error parsing SSE message:', e);
                    }
                };

                eventSource.onerror = (error) => {
                    console.error('SSE error:', error);
                    eventSource.close();
                    currentSearchEventSource = null;
                    // Resolve with whatever we have so far
                    resolve(accumulatedData);
                };
            });
        }

        // Function to handle POST streaming requests (for large payloads like research reports)
        // Bug #23: Added abortSignal parameter for cancellation support
        // Progressive rendering: Added callbacks parameter for real-time UI updates
        async function handlePostStreamingRequest(url, body, query, abortSignal = null, callbacks = {}) {
            const { onArticles, onSummary, onAnswer, onComplete, onProgress } = callbacks;
            const fetchOptions = {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream'
                },
                body: JSON.stringify(body)
            };
            if (abortSignal) fetchOptions.signal = abortSignal;
            const response = await fetch(url, fetchOptions);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let accumulatedData = {};
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // Process complete SSE messages (separated by double newlines)
                const messages = buffer.split('\n\n');
                buffer = messages.pop(); // Keep incomplete message in buffer

                for (const message of messages) {
                    if (!message.trim()) continue;

                    // Parse SSE format: "data: {...}"
                    const lines = message.split('\n');
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6));
                                console.log('POST SSE message received:', data);

                                switch(data.message_type) {
                                    case 'begin-nlweb-response':
                                        if (data.query_id) {
                                            currentAnalyticsQueryId = data.query_id;
                                            console.log('[Analytics] Using backend query_id:', currentAnalyticsQueryId);
                                        }
                                        if (data.conversation_id) {
                                            currentConversationId = data.conversation_id;
                                            console.log('[Conversation] Using backend conversation_id:', currentConversationId);
                                        }
                                        break;

                                    case 'remember':
                                        if (data.item_to_remember) {
                                            showMemoryNotification(data.item_to_remember);
                                        }
                                        break;

                                    case 'time_filter_relaxed':
                                        console.warn('[Temporal] Time filter relaxed:', data.content);
                                        showTimeFilterRelaxedWarning(data.content);
                                        break;

                                    case 'progress':
                                        console.log('[Progress]', data.stage, data.message);
                                        if (onProgress) onProgress(data.stage, data.message, data.percent);
                                        break;

                                    // Unified mode message types
                                    case 'articles':
                                        accumulatedData.content = data.content || [];
                                        if (onArticles) onArticles(accumulatedData.content);
                                        break;
                                    case 'summary':
                                        accumulatedData.summary = { message: data.content };
                                        if (onSummary) onSummary(accumulatedData.summary, accumulatedData.content?.length || 0);
                                        break;
                                    case 'answer':
                                        // Received twice (initial + enriched), idempotent overwrite
                                        accumulatedData.nlws = data.answer ? { answer: data.answer } : null;
                                        if (onAnswer) onAnswer(accumulatedData.nlws, accumulatedData.content?.length || 0);
                                        break;
                                    case 'end-nlweb-response':
                                        // Explicit no-op — stream ends on 'complete'
                                        break;

                                    case 'complete':
                                        console.log('POST Stream complete. Accumulated data:', accumulatedData);
                                        if (onComplete) onComplete(accumulatedData);
                                        return accumulatedData;

                                    default:
                                        Object.assign(accumulatedData, data);
                                        break;
                                }
                            } catch (e) {
                                console.error('Error parsing POST SSE message:', e, line);
                            }
                        }
                    }
                }
            }

            return accumulatedData;
        }

        // Function to update Deep Research progress display - Log Style
        function updateReasoningProgress(data) {
            console.log('[Progress] updateReasoningProgress called with stage:', data.stage);
            let container = document.getElementById('reasoning-progress');

            // Create container if doesn't exist
            if (!container) {
                console.log('[Progress] Creating new log-style progress container');
                container = document.createElement('div');
                container.id = 'reasoning-progress';
                container.className = 'reasoning-progress-container';
                container.innerHTML = `
                    <div class="progress-header">深度研究進行中</div>
                    <div class="progress-log" id="progress-log"></div>
                `;

                // Insert into loading state (which is visible during Deep Research)
                const loadingState = document.getElementById('loadingState');
                if (loadingState) {
                    loadingState.appendChild(container);
                } else {
                    // Fallback: Insert before results
                    const resultsSection = document.getElementById('results');
                    if (resultsSection) {
                        resultsSection.insertBefore(container, resultsSection.firstChild);
                    }
                }
            }

            const logContainer = document.getElementById('progress-log');
            if (!logContainer) return;

            const stage = data.stage;

            // Helper to add a log entry (no detail parameter)
            function addLogEntry(icon, text, cssClass = '') {
                // Check if we should update an existing active entry instead of adding new
                const existingActive = logContainer.querySelector('.log-entry.active');
                if (existingActive && cssClass === 'complete') {
                    existingActive.classList.remove('active');
                    existingActive.classList.add('complete');
                    existingActive.querySelector('.log-icon').textContent = icon;
                    return;
                }

                const entry = document.createElement('div');
                entry.className = `log-entry ${cssClass}`;
                entry.innerHTML = `
                    <span class="log-icon">${icon}</span>
                    <span class="log-text">${text}</span>
                `;
                logContainer.appendChild(entry);

                // Auto-scroll to bottom
                container.scrollTop = container.scrollHeight;
            }

            // Helper to mark last active as complete
            function completeLastActive(icon = '✓') {
                const lastActive = logContainer.querySelector('.log-entry.active:last-of-type');
                if (lastActive) {
                    lastActive.classList.remove('active');
                    lastActive.classList.add('complete');
                    lastActive.querySelector('.log-icon').textContent = icon;
                }
            }

            // Stage-specific handling
            switch (stage) {
                case 'analyst_analyzing':
                    const iterInfo = data.iteration && data.total_iterations
                        ? ` (${data.iteration}/${data.total_iterations})`
                        : '';
                    addLogEntry('○', `正在深度分析資料來源${iterInfo}...`, 'active');
                    break;

                case 'analyst_complete':
                    completeLastActive('✓');
                    addLogEntry('✓', `分析完成`, 'complete');
                    break;

                case 'gap_search_started':
                    addLogEntry('↻', `偵測到資訊缺口，正在補充搜尋...`, 'active gap-search');
                    break;

                case 'cov_verifying':
                    addLogEntry('○', '正在驗證事實宣稱...', 'active cov');
                    break;

                case 'cov_complete':
                    completeLastActive('✓');
                    addLogEntry('✓', '事實查核完成', 'complete cov');
                    break;

                case 'critic_reviewing':
                    addLogEntry('○', '正在檢查邏輯與來源可信度...', 'active');
                    break;

                case 'critic_complete':
                    completeLastActive();
                    const status = data.status || 'PASS';
                    const statusIcon = status === 'PASS' ? '✓' : status === 'WARN' ? '⚠' : '✗';
                    const statusClass = status === 'PASS' ? 'complete' : status === 'WARN' ? 'warning' : 'error';
                    const statusText = status === 'PASS' ? '審查通過' : status === 'WARN' ? '審查通過（有警告）' : '需要修改';
                    addLogEntry(statusIcon, statusText, statusClass);
                    break;

                case 'writer_planning':
                    addLogEntry('○', '正在規劃報告結構...', 'active');
                    break;

                case 'writer_composing':
                    completeLastActive('✓');
                    addLogEntry('○', '正在撰寫最終報告...', 'active');
                    break;

                case 'writer_complete':
                    completeLastActive('✓');
                    addLogEntry('✓', '報告生成完成', 'complete');
                    // Change header indicator to done
                    const header = container.querySelector('.progress-header');
                    if (header) {
                        header.style.setProperty('--blink-color', '#22c55e');
                    }
                    break;

                default:
                    console.log('[Progress] Unknown stage:', stage);
                    break;
            }
        }

        // Function to show memory notification
        function showMemoryNotification(itemToRemember) {
            // Create notification element
            const notification = document.createElement('div');
            notification.className = 'memory-notification';
            notification.innerHTML = `
                <span class="memory-icon">💾</span>
                <span class="memory-text">我會記住：「${escapeHTML(itemToRemember)}」</span>
            `;

            // Add to results section or create a notification area
            let notificationArea = document.getElementById('memoryNotificationArea');
            if (!notificationArea) {
                notificationArea = document.createElement('div');
                notificationArea.id = 'memoryNotificationArea';
                notificationArea.style.cssText = 'margin-bottom: 20px;';
                resultsSection.insertBefore(notificationArea, resultsSection.firstChild);
            }

            notificationArea.appendChild(notification);

            // Auto-hide after 5 seconds with fade out
            setTimeout(() => {
                notification.style.opacity = '0';
                setTimeout(() => notification.remove(), 300);
            }, 5000);
        }

        // Function to show time filter relaxed warning banner
        function showTimeFilterRelaxedWarning(message) {
            // Remove existing warning if present
            const existing = document.getElementById('timeFilterWarning');
            if (existing) existing.remove();

            const warning = document.createElement('div');
            warning.id = 'timeFilterWarning';
            warning.className = 'time-filter-warning';
            warning.innerHTML = `<span class="warning-text">${escapeHTML(message)}</span>`;

            // Insert at top of results section
            resultsSection.insertBefore(warning, resultsSection.firstChild);
        }

        // Function to populate UI from API response
        function populateResultsFromAPI(data, query) {
            // Get articles from response - prioritize content/results for summarize mode
            const articles = data.content || data.results || (data.nlws && data.nlws.items) || [];

            // Populate AI Summary section at the top
            const aiSummarySection = document.getElementById('aiSummarySection');
            const aiSummaryContent = document.getElementById('aiSummaryContent');

            if (!aiSummarySection || !aiSummaryContent) {
                console.warn('[populateResultsFromAPI] aiSummarySection or aiSummaryContent not found in DOM');
            } else if (data.summary && data.summary.message) {
                // We have a summary (from summarize mode)
                aiSummaryContent.innerHTML = `
                    <div class="summary-section">
                        <div class="summary-content">${escapeHTML(data.summary.message)}</div>
                    </div>
                    <div class="summary-footer">
                        <div class="source-info">⚠️ 資料來源：基於 ${articles.length} 則報導生成</div>
                        <div class="feedback-buttons">
                            <button class="btn-feedback" data-rating="positive">👍 有幫助</button>
                            <button class="btn-feedback" data-rating="negative">👎 不準確</button>
                        </div>
                    </div>
                `;
                aiSummarySection.style.display = 'block';
            } else if (data.nlws && data.nlws.answer) {
                // We have an AI-generated answer (from generate mode)
                // Convert markdown links to HTML and preserve <br> tags for proper rendering
                const formattedAnswer = convertMarkdownToHtml(data.nlws.answer);
                aiSummaryContent.innerHTML = `
                    <div class="summary-section">
                        <div class="summary-content">${formattedAnswer}</div>
                    </div>
                    <div class="summary-footer">
                        <div class="source-info">⚠️ 資料來源：基於 ${articles.length} 則報導生成</div>
                        <div class="feedback-buttons">
                            <button class="btn-feedback" data-rating="positive">👍 有幫助</button>
                            <button class="btn-feedback" data-rating="negative">👎 不準確</button>
                        </div>
                    </div>
                `;
                aiSummarySection.style.display = 'block';
            } else {
                if (aiSummarySection) aiSummarySection.style.display = 'none';
            }

            // Clear existing list view content
            listView.innerHTML = '';
            timelineView.innerHTML = '';

            if (articles.length === 0) {
                listView.innerHTML = '<div class="news-card"><div class="news-title">沒有找到相關文章</div></div>';
                console.warn('No articles found in API response');
                return;
            }

            // Group articles by date for timeline view
            const articlesByDate = {};

            // Sort articles by score in descending order (highest score first)
            articles.sort((a, b) => {
                const scoreA = a.score || a.metadata?.score || 0;
                const scoreB = b.score || b.metadata?.score || 0;
                return scoreB - scoreA;
            });

            // Populate news cards
            articles.forEach((article, index) => {
                const schema = article.schema_object || article;
                // Score might be at article.score or article.metadata.score
                let rawScore = article.score || article.metadata?.score || 0;

                // If score is > 1, it's already a percentage (e.g., 85)
                // If score is <= 1, it's a decimal (e.g., 0.85) and needs to be multiplied by 100
                const relevancePercent = rawScore > 1 ? Math.round(rawScore) : Math.round(rawScore * 100);

                // For star calculation, normalize to 0-1 range
                const normalizedScore = rawScore > 1 ? rawScore / 100 : rawScore;
                const stars = Math.min(5, Math.max(1, Math.round(normalizedScore * 5)));
                const starsHTML = '★'.repeat(stars) + '☆'.repeat(5 - stars);

                // Extract data with fallbacks
                const title = schema.headline || schema.name || '無標題';

                // Try multiple locations for publisher/source
                let publisher = '未知來源';
                if (schema.publisher?.name) {
                    publisher = schema.publisher.name;
                } else if (schema.publisher && typeof schema.publisher === 'string') {
                    publisher = schema.publisher;
                } else if (article.site) {
                    // Use the site field if available (e.g., "ithome")
                    publisher = article.site.charAt(0).toUpperCase() + article.site.slice(1); // Capitalize first letter
                } else if (schema.author) {
                    if (Array.isArray(schema.author) && schema.author.length > 0) {
                        publisher = schema.author[0].name || schema.author[0];
                    } else if (typeof schema.author === 'string') {
                        publisher = schema.author;
                    }
                }

                const datePublished = schema.datePublished || new Date().toISOString();
                const date = new Date(datePublished).toISOString().split('T')[0];
                const description = schema.description || article.description || '';
                const url = schema.url || '#';

                // Check if this article is already pinned
                const isPinned = pinnedNewsCards.some(p => p.url === url);

                // Create card for list view
                const cardHTML = `
                    <div class="news-card" data-url="${escapeHTML(url)}" data-title="${escapeHTML(title)}" data-description="${escapeHTML(description)}">
                        <div class="news-title">${escapeHTML(title)}</div>
                        <div class="news-meta">
                            <span>🏢 ${escapeHTML(publisher)}</span>
                            <span>📅 ${date}</span>
                            <div class="relevance">
                                <span class="stars">${starsHTML}</span>
                                <span>相關度 ${relevancePercent}%</span>
                            </div>
                        </div>
                        ${description ? `<div class="news-excerpt">${escapeHTML(description)}</div>` : ''}
                        <div class="news-card-footer">
                            <a href="${escapeHTML(url)}" class="btn-read-more" target="_blank">閱讀全文 →</a>
                            <button class="news-card-pin ${isPinned ? 'pinned' : ''}" title="${isPinned ? '取消釘選' : '釘選新聞'}">📌</button>
                        </div>
                    </div>
                `;

                listView.innerHTML += cardHTML;

                // Group by date for timeline view
                if (!articlesByDate[date]) {
                    articlesByDate[date] = [];
                }
                articlesByDate[date].push({
                    title, publisher, description, url, starsHTML, relevancePercent, isPinned
                });
            });

            // Populate timeline view
            const sortedDates = Object.keys(articlesByDate).sort().reverse();
            sortedDates.forEach(date => {
                const dateArticles = articlesByDate[date];
                const timelineHTML = `
                    <div class="timeline-date">
                        <div class="timeline-dot"></div>
                        <div class="date-label">${date}</div>
                        ${dateArticles.map(art => `
                            <div class="news-card" data-url="${escapeHTML(art.url)}" data-title="${escapeHTML(art.title)}">
                                <div class="news-title">${escapeHTML(art.title)}</div>
                                <div class="news-meta">
                                    <span>🏢 ${escapeHTML(art.publisher)}</span>
                                    <div class="relevance">
                                        <span class="stars">${art.starsHTML}</span>
                                        <span>相關度 ${art.relevancePercent}%</span>
                                    </div>
                                </div>
                                ${art.description ? `<div class="news-excerpt">${escapeHTML(art.description)}</div>` : ''}
                                <div class="news-card-footer">
                                    <a href="${escapeHTML(art.url)}" class="btn-read-more" target="_blank">閱讀全文 →</a>
                                    <button class="news-card-pin ${art.isPinned ? 'pinned' : ''}" title="${art.isPinned ? '取消釘選' : '釘選新聞'}">📌</button>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                `;
                timelineView.innerHTML += timelineHTML;
            });
        }

        // === Progressive Rendering Functions ===

        // Render skeleton placeholder cards
        function renderSkeletonCards(count = 5) {
            const listView = document.getElementById('listView');
            if (!listView) return;

            listView.innerHTML = '';
            for (let i = 0; i < count; i++) {
                const skeleton = document.createElement('div');
                skeleton.className = 'skeleton-card';
                skeleton.innerHTML = `
                    <div class="skeleton-line skeleton-title"></div>
                    <div class="skeleton-line skeleton-meta"></div>
                    <div class="skeleton-line skeleton-excerpt"></div>
                    <div class="skeleton-line skeleton-excerpt"></div>
                `;
                listView.appendChild(skeleton);
            }
            console.log(`[Progressive] Rendered ${count} skeleton cards`);
        }

        // Render skeleton + typing indicator for AI summary area
        function renderSummarySkeleton() {
            const aiSummarySection = document.getElementById('aiSummarySection');
            const aiSummaryContent = document.getElementById('aiSummaryContent');
            if (!aiSummarySection || !aiSummaryContent) return;

            aiSummaryContent.innerHTML = `
                <div class="skeleton-summary">
                    <div class="skeleton-line skeleton-summary-header"></div>
                    <div class="skeleton-line skeleton-summary-line"></div>
                    <div class="skeleton-line skeleton-summary-line"></div>
                    <div class="skeleton-line skeleton-summary-line"></div>
                </div>
                <div class="ai-typing-indicator" id="progressIndicator">
                    <div class="ai-typing-dot"></div>
                    <div class="ai-typing-dot"></div>
                    <div class="ai-typing-dot"></div>
                    <span id="progressMessage" style="margin-left: 8px; color: #666;">正在處理您的查詢...</span>
                </div>
            `;
            aiSummarySection.style.display = 'block';
            console.log('[Progressive] Rendered summary skeleton');
        }

        // Update progress indicator message
        function updateProgressMessage(message) {
            const progressMsg = document.getElementById('progressMessage');
            if (progressMsg) {
                progressMsg.textContent = message;
                console.log('[Progressive] Updated progress message:', message);
            }
        }

        // Create a single article card DOM element
        function createArticleCard(article, index) {
            const schema = article.schema_object || article;
            let rawScore = article.score || article.metadata?.score || 0;

            const relevancePercent = rawScore > 1 ? Math.round(rawScore) : Math.round(rawScore * 100);
            const normalizedScore = rawScore > 1 ? rawScore / 100 : rawScore;
            const stars = Math.min(5, Math.max(1, Math.round(normalizedScore * 5)));
            const starsHTML = '\u2605'.repeat(stars) + '\u2606'.repeat(5 - stars);

            const title = schema.headline || schema.name || '無標題';

            let publisher = '未知來源';
            if (schema.publisher?.name) {
                publisher = schema.publisher.name;
            } else if (schema.publisher && typeof schema.publisher === 'string') {
                publisher = schema.publisher;
            } else if (article.site) {
                publisher = article.site.charAt(0).toUpperCase() + article.site.slice(1);
            } else if (schema.author) {
                if (Array.isArray(schema.author) && schema.author.length > 0) {
                    publisher = schema.author[0].name || schema.author[0];
                } else if (typeof schema.author === 'string') {
                    publisher = schema.author;
                }
            }

            const datePublished = schema.datePublished || new Date().toISOString();
            const date = new Date(datePublished).toISOString().split('T')[0];
            const description = schema.description || article.description || '';
            const url = schema.url || '#';
            const isPinned = pinnedNewsCards.some(p => p.url === url);

            const card = document.createElement('div');
            card.className = 'news-card progressive-fade-in';
            card.setAttribute('data-url', url);
            card.setAttribute('data-title', title);
            card.setAttribute('data-description', description);

            card.innerHTML = `
                <div class="news-title">${escapeHTML(title)}</div>
                <div class="news-meta">
                    <span>\uD83C\uDFE2 ${escapeHTML(publisher)}</span>
                    <span>\uD83D\uDCC5 ${date}</span>
                    <div class="relevance">
                        <span class="stars">${starsHTML}</span>
                        <span>相關度 ${relevancePercent}%</span>
                    </div>
                </div>
                ${description ? `<div class="news-excerpt">${escapeHTML(description)}</div>` : ''}
                <div class="news-card-footer">
                    <a href="${escapeHTML(url)}" class="btn-read-more" target="_blank">閱讀全文 \u2192</a>
                    <button class="news-card-pin ${isPinned ? 'pinned' : ''}" title="${isPinned ? '取消釘選' : '釘選新聞'}">\uD83D\uDCCC</button>
                </div>
            `;

            return { card, date, title, publisher, description, url, starsHTML, relevancePercent, isPinned };
        }

        // Progressively render articles replacing skeletons
        function renderArticlesProgressive(articles) {
            const listView = document.getElementById('listView');
            const timelineView = document.getElementById('timelineView');
            if (!listView) return;

            // Clear skeleton cards
            listView.innerHTML = '';
            if (timelineView) timelineView.innerHTML = '';

            if (!articles || articles.length === 0) {
                listView.innerHTML = '<div class="news-card"><div class="news-title">沒有找到相關文章</div></div>';
                console.warn('[Progressive] No articles to render');
                return;
            }

            // Sort by score
            articles.sort((a, b) => {
                const scoreA = a.score || a.metadata?.score || 0;
                const scoreB = b.score || b.metadata?.score || 0;
                return scoreB - scoreA;
            });

            const articlesByDate = {};

            articles.forEach((article, index) => {
                const { card, date, title, publisher, description, url, starsHTML, relevancePercent, isPinned } = createArticleCard(article, index);
                listView.appendChild(card);

                // Group for timeline
                if (!articlesByDate[date]) {
                    articlesByDate[date] = [];
                }
                articlesByDate[date].push({ title, publisher, description, url, starsHTML, relevancePercent, isPinned });
            });

            // Populate timeline view
            if (timelineView) {
                const sortedDates = Object.keys(articlesByDate).sort().reverse();
                sortedDates.forEach(date => {
                    const dateArticles = articlesByDate[date];
                    const timelineHTML = `
                        <div class="timeline-date">
                            <div class="timeline-dot"></div>
                            <div class="date-label">${date}</div>
                            ${dateArticles.map(art => `
                                <div class="news-card progressive-fade-in" data-url="${escapeHTML(art.url)}" data-title="${escapeHTML(art.title)}">
                                    <div class="news-title">${escapeHTML(art.title)}</div>
                                    <div class="news-meta">
                                        <span>\uD83C\uDFE2 ${escapeHTML(art.publisher)}</span>
                                        <div class="relevance">
                                            <span class="stars">${art.starsHTML}</span>
                                            <span>相關度 ${art.relevancePercent}%</span>
                                        </div>
                                    </div>
                                    ${art.description ? `<div class="news-excerpt">${escapeHTML(art.description)}</div>` : ''}
                                    <div class="news-card-footer">
                                        <a href="${escapeHTML(art.url)}" class="btn-read-more" target="_blank">閱讀全文 \u2192</a>
                                        <button class="news-card-pin ${art.isPinned ? 'pinned' : ''}" title="${art.isPinned ? '取消釘選' : '釘選新聞'}">\uD83D\uDCCC</button>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    `;
                    timelineView.innerHTML += timelineHTML;
                });
            }

            console.log(`[Progressive] Rendered ${articles.length} articles`);
        }

        // Progressively render AI answer (supports initial + enriched updates)
        function renderAnswerProgressive(answerData, articleCount) {
            const aiSummarySection = document.getElementById('aiSummarySection');
            const aiSummaryContent = document.getElementById('aiSummaryContent');
            if (!aiSummarySection || !aiSummaryContent) return;

            if (!answerData || !answerData.answer) {
                aiSummarySection.style.display = 'none';
                return;
            }

            const formattedAnswer = convertMarkdownToHtml(answerData.answer);
            const isUpdate = aiSummaryContent.querySelector('.summary-content') !== null &&
                             !aiSummaryContent.querySelector('.skeleton-summary');

            aiSummaryContent.innerHTML = `
                <div class="summary-section ${isUpdate ? 'content-updated' : 'progressive-fade-in'}">
                    <div class="summary-content">${formattedAnswer}</div>
                </div>
                <div class="summary-footer">
                    <div class="source-info">\u26A0\uFE0F 資料來源：基於 ${articleCount} 則報導生成</div>
                    <div class="feedback-buttons">
                        <button class="btn-feedback" data-rating="positive">\uD83D\uDC4D 有幫助</button>
                        <button class="btn-feedback" data-rating="negative">\uD83D\uDC4E 不準確</button>
                    </div>
                </div>
            `;
            aiSummarySection.style.display = 'block';

            console.log(`[Progressive] Rendered AI answer (update: ${isUpdate})`);
        }

        // Clear all loading states
        function clearLoadingStates() {
            const loadingState = document.getElementById('loadingState');
            if (loadingState) loadingState.classList.remove('active');

            // Remove any remaining skeleton elements
            document.querySelectorAll('.skeleton-card, .skeleton-summary, .ai-typing-indicator').forEach(el => el.remove());

            console.log('[Progressive] Cleared all loading states');
        }

        // === End Progressive Rendering Functions ===

        // Helper function to escape HTML
        function escapeHTML(str) {
            if (!str) return '';
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }

        // Convert markdown-style links to HTML and preserve HTML line breaks
        // Converts [來源](url) to clickable <a> tags while keeping <br> tags
        function convertMarkdownToHtml(text) {
            if (!text) return '';

            // First escape any potentially dangerous HTML except <br> tags
            let safe = text
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;");

            // Restore <br> tags
            safe = safe.replace(/&lt;br&gt;/g, "<br>");

            // Convert markdown links [text](url) to HTML <a> tags
            // Pattern: [any text](url)
            safe = safe.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function(match, text, url) {
                // Decode HTML entities in the URL that we encoded earlier
                const decodedUrl = url
                    .replace(/&amp;/g, "&")
                    .replace(/&lt;/g, "<")
                    .replace(/&gt;/g, ">");

                return `<a href="${decodedUrl}" class="source-link" target="_blank" rel="noopener noreferrer">${text}</a>`;
            });

            return safe;
        }

        // Search functionality
        btnSearch.addEventListener('click', performSearch);
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
                e.preventDefault();
                // Bug #23: Prevent duplicate sends during processing
                if (searchInput.dataset.processing === 'true') return;
                performSearch();
            }
        });

        // Cancel any in-flight search to prevent stale results from corrupting UI
        function cancelActiveSearch() {
            searchGenerationId++;
            if (currentSearchAbortController) {
                currentSearchAbortController.abort();
                currentSearchAbortController = null;
            }
            if (currentSearchEventSource) {
                currentSearchEventSource.close();
                currentSearchEventSource = null;
            }
            loadingState.classList.remove('active');
        }

        // Bug #23: Cancel all active requests across all modes (search, DR, FC)
        function cancelAllActiveRequests() {
            cancelActiveSearch();
            if (currentDeepResearchEventSource) {
                currentDeepResearchEventSource.close();
                currentDeepResearchEventSource = null;
            }
            if (currentFreeConvAbortController) {
                currentFreeConvAbortController.abort();
                currentFreeConvAbortController = null;
            }
            // Reset UI loading states
            loadingState.classList.remove('active');
            const chatLoadingEl = document.getElementById('chatLoading');
            if (chatLoadingEl) chatLoadingEl.classList.remove('active');
        }

        // Bug #23: UI state machine — toggle between idle and processing states
        function setProcessingState(isProcessing) {
            const searchBtn = document.getElementById('btnSearch');
            const stopBtn = document.getElementById('btnStopGenerate');
            if (isProcessing) {
                if (searchBtn) searchBtn.style.display = 'none';
                if (stopBtn) stopBtn.style.display = '';
                // Disable Enter key submission during processing
                searchInput.dataset.processing = 'true';
            } else {
                if (searchBtn) searchBtn.style.display = '';
                if (stopBtn) stopBtn.style.display = 'none';
                searchInput.dataset.processing = '';
            }
        }

        // Bug #23: Stop button click handler
        document.addEventListener('DOMContentLoaded', () => {
            const stopBtn = document.getElementById('btnStopGenerate');
            if (stopBtn) {
                stopBtn.addEventListener('click', () => {
                    cancelAllActiveRequests();
                    setProcessingState(false);
                });
            }
        });

        async function performSearch() {
            const query = searchInput.value.trim();
            if (!query) return;

            // Bug #23: Cancel all active requests (search, DR, FC) before starting new search
            cancelAllActiveRequests();
            setProcessingState(true);
            const mySearchGeneration = searchGenerationId;
            currentSearchAbortController = new AbortController();

            // Note: Analytics will be initialized when we receive 'begin-nlweb-response' from backend
            // with the server-generated query_id

            // Hide initial state and folder page
            initialState.style.display = 'none';
            const folderPageSearch = document.getElementById('folderPage');
            if (folderPageSearch) folderPageSearch.style.display = 'none';

            // Check current mode
            if (currentMode === 'chat') {
                // Free conversation mode - no search, just chat
                await performFreeConversation(query);
                return;
            }

            if (currentMode === 'deep_research') {
                // 如果未確認進階搜尋設定，先彈出 popup
                if (!advancedSearchConfirmed) {
                    setProcessingState(false);
                    showAdvancedPopup();
                    return;
                }
                // Deep Research mode - use Actor-Critic reasoning
                await performDeepResearch(query);
                return;
            }

            // Search mode - unified SSE flow with progressive rendering
            // Phase 3: Immediately show skeleton placeholders
            loadingState.classList.add('active');
            resultsSection.classList.add('active');
            renderSkeletonCards(5);
            renderSummarySkeleton();
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

            try {
                const prevQueriesForThisTurn = [...conversationHistory];

                // Save session immediately on query submit (before waiting for results)
                conversationHistory.push(query);
                saveCurrentSession();

                // Single unified POST SSE call
                const body = {
                    query: query,
                    site: getSelectedSitesParam(),
                    generate_mode: 'unified',
                    streaming: 'true',
                    session_id: currentSessionId
                };
                if (prevQueriesForThisTurn.length > 0) {
                    body.prev = JSON.stringify(prevQueriesForThisTurn);
                }

                // Phase 4: Progressive rendering callbacks
                const callbacks = {
                    onProgress: (stage, message, percent) => {
                        if (mySearchGeneration !== searchGenerationId) return;
                        updateProgressMessage(message);
                    },
                    onArticles: (articles) => {
                        if (mySearchGeneration !== searchGenerationId) return;
                        console.log('[Progressive] Articles received:', articles.length);
                        renderArticlesProgressive(articles);
                        loadingState.classList.remove('active');
                    },
                    onAnswer: (answerData, articleCount) => {
                        if (mySearchGeneration !== searchGenerationId) return;
                        if (answerData?.answer) {
                            console.log('[Progressive] Answer received');
                            renderAnswerProgressive(answerData, articleCount);
                        }
                    },
                    onComplete: () => {
                        if (mySearchGeneration !== searchGenerationId) return;
                        console.log('[Progressive] Stream complete');
                        clearLoadingStates();
                    }
                };

                const combinedData = await handlePostStreamingRequest(
                    '/ask', body, query, currentSearchAbortController.signal, callbacks
                );

                // Stale check
                if (mySearchGeneration !== searchGenerationId) {
                    console.log('[Search] Stale search discarded before rendering');
                    return;
                }

                console.log('Unified Combined Data:', combinedData);

                // Note: UI is already populated progressively via callbacks
                // populateResultsFromAPI is no longer needed for Search mode

                // Store complete session data for this query
                sessionHistory.push({
                    query: query,
                    data: combinedData,
                    timestamp: Date.now()
                });

                // Accumulate articles from this search for chat mode
                if (combinedData.content && combinedData.content.length > 0) {
                    const existingUrls = new Set(accumulatedArticles.map(art => art.url || art.schema_object?.url));
                    const newArticles = combinedData.content.filter(art => {
                        const url = art.url || art.schema_object?.url;
                        return url && !existingUrls.has(url);
                    });
                    accumulatedArticles.push(...newArticles);
                    console.log(`Accumulated ${newArticles.length} new articles, total: ${accumulatedArticles.length}`);
                }

                // Trim history if too long
                if (conversationHistory.length > 10) {
                    conversationHistory.shift();
                    sessionHistory.shift();
                }

                renderConversationHistory();
                saveCurrentSession();

                setProcessingState(false);
                // resultsSection already active from skeleton phase
            } catch (error) {
                setProcessingState(false);
                clearLoadingStates();
                if (error.name === 'AbortError' || mySearchGeneration !== searchGenerationId) {
                    console.log('[Search] Search cancelled or superseded');
                    return;
                }
                console.error('Search failed:', error);
                // Show error in list view instead of alert for better UX
                const listView = document.getElementById('listView');
                if (listView) {
                    listView.innerHTML = `<div class="news-card"><div class="news-title">搜尋失敗</div><div class="news-excerpt">${escapeHTML(error.message)}</div></div>`;
                }
            }
        }

        // Deep Research Mode function
        async function performDeepResearch(query, skipClarification = false, comprehensiveSearch = false, userTimeRange = null, userTimeLabel = null) {
            console.log('=== Deep Research Mode ===');
            console.log('Query:', query);
            console.log('Skip clarification:', skipClarification);
            console.log('Comprehensive search:', comprehensiveSearch);
            console.log('User time range:', userTimeRange);
            console.log('User time label:', userTimeLabel);

            // Save query before clearing (for conversation history)
            const savedQuery = query;

            // Clear input
            searchInput.value = '';
            setProcessingState(true); // Bug #23

            // Save session immediately on first query submit (skip for clarification re-submit)
            if (!skipClarification) {
                conversationHistory.push(query);
                saveCurrentSession();
            }

            // Enable chat container for conversational clarification
            const chatContainer = document.getElementById('chatContainer');
            const chatMessagesEl = document.getElementById('chatMessages');
            if (chatContainer) {
                chatContainer.classList.add('active');
                console.log('[Deep Research] Chat container activated');

                // Add user message to chat
                if (chatMessagesEl) {
                    const userMessageDiv = document.createElement('div');
                    userMessageDiv.className = 'chat-message user';
                    userMessageDiv.innerHTML = `
                        <div class="chat-message-header">你</div>
                        <div class="chat-message-bubble">${escapeHTML(query)}</div>
                    `;
                    chatMessagesEl.appendChild(userMessageDiv);
                    chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
                    console.log('[Deep Research] User message added to chat');
                }
            }

            try {
                const base = window.location.origin;

                // Call Deep Research API with SSE streaming
                const deepResearchUrl = new URL('/api/deep_research', base);
                deepResearchUrl.searchParams.append('query', query);
                deepResearchUrl.searchParams.append('site', getSelectedSitesParam());
                deepResearchUrl.searchParams.append('research_mode', currentResearchMode); // User-selected mode
                deepResearchUrl.searchParams.append('max_iterations', '3');

                // Add skip_clarification flag (critical for avoiding infinite loops)
                if (skipClarification) {
                    deepResearchUrl.searchParams.append('skip_clarification', 'true');
                    console.log('[Deep Research] Skip clarification enabled');
                }

                // Add comprehensive_search flag for MMR tuning
                if (comprehensiveSearch) {
                    deepResearchUrl.searchParams.append('comprehensive_search', 'true');
                    console.log('[Deep Research] Comprehensive search enabled (high diversity)');
                }

                // Add user-selected time range (BINDING constraint for Analyst)
                if (userTimeRange && userTimeRange.start && userTimeRange.end) {
                    deepResearchUrl.searchParams.append('time_range_start', userTimeRange.start);
                    deepResearchUrl.searchParams.append('time_range_end', userTimeRange.end);
                    deepResearchUrl.searchParams.append('user_selected_time', 'true');
                    if (userTimeLabel) {
                        deepResearchUrl.searchParams.append('user_time_label', userTimeLabel);
                    }
                    console.log('[Deep Research] User-selected time range:', userTimeRange.start, 'to', userTimeRange.end);
                }

                // Add enable_kg flag (Phase KG)
                const kgToggle = document.getElementById('kgToggle');
                if (kgToggle && kgToggle.checked) {
                    deepResearchUrl.searchParams.append('enable_kg', 'true');
                    console.log('[Deep Research] Knowledge Graph generation enabled');
                }

                // Add enable_web_search flag (Stage 5)
                const webSearchToggle = document.getElementById('webSearchToggle');
                if (webSearchToggle && webSearchToggle.checked) {
                    deepResearchUrl.searchParams.append('enable_web_search', 'true');
                    console.log('[Deep Research] Web Search enabled');
                }

                // Add session_id for analytics and A/B testing
                deepResearchUrl.searchParams.append('session_id', currentSessionId);

                // Add conversation_id for context continuity across modes
                if (currentConversationId) {
                    deepResearchUrl.searchParams.append('conversation_id', currentConversationId);
                    console.log('[Deep Research] Using existing conversation_id:', currentConversationId);
                }

                // Add private sources parameters if enabled
                if (includePrivateSources) {
                    deepResearchUrl.searchParams.append('include_private_sources', 'true');
                    deepResearchUrl.searchParams.append('user_id', TEMP_USER_ID);
                    console.log('[Deep Research] Private sources enabled for user:', TEMP_USER_ID);
                }

                console.log('Deep Research URL:', deepResearchUrl.toString());

                // Bug #23: Cancel any previous active requests before starting DR
                cancelAllActiveRequests();

                // Show loading AFTER cancelAllActiveRequests (which removes .active)
                loadingState.classList.add('active');

                // Clean up any stale progress container from previous requests
                const oldProgress = document.getElementById('reasoning-progress');
                if (oldProgress) oldProgress.remove();

                // Use SSE streaming to get progress updates
                const eventSource = new EventSource(deepResearchUrl.toString());
                currentDeepResearchEventSource = eventSource; // Bug #23: store for external abort

                let fullReport = '';
                let progressContainer = null;

                eventSource.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        console.log('Deep Research SSE:', data);

                        // Handle different message types
                        if (data.message_type === 'begin-nlweb-response') {
                            // Query started - capture conversation_id
                            if (data.conversation_id) {
                                currentConversationId = data.conversation_id;
                                console.log('[Deep Research] Using backend conversation_id:', currentConversationId);
                            }
                        } else if (data.message_type === 'clarification_required') {
                            // Phase 4: Clarification needed before proceeding (conversational)
                            console.log('[Clarification] Request received:', data.clarification);
                            addClarificationMessage(data.clarification, data.query, eventSource, savedQuery);
                        } else if (data.message_type === 'intermediate_result') {
                            // Progress update - show reasoning progress
                            updateReasoningProgress(data);
                        } else if (data.message_type === 'final_result') {
                            // Final report received
                            fullReport = data.final_report || '';

                            // Close event source
                            eventSource.close();
                            currentDeepResearchEventSource = null;

                            // Hide loading
                            loadingState.classList.remove('active');
                            setProcessingState(false); // Bug #23

                            // Display results
                            displayDeepResearchResults(fullReport, data, savedQuery);

                            // 自動建立/更新 session
                            saveCurrentSession();
                        } else if (data.message_type === 'complete') {
                            // Stream complete - close connection
                            eventSource.close();
                            currentDeepResearchEventSource = null;
                            setProcessingState(false); // Bug #23
                            console.log('Deep Research stream complete');
                        } else if (data.message_type === 'error') {
                            console.error('Deep Research error:', data.error);
                            eventSource.close();
                            currentDeepResearchEventSource = null;
                            loadingState.classList.remove('active');
                            setProcessingState(false); // Bug #23
                            alert('Deep Research 發生錯誤: ' + data.error);
                        }
                    } catch (e) {
                        console.error('Failed to parse SSE data:', e);
                    }
                };

                eventSource.onerror = (error) => {
                    console.error('SSE connection error:', error);
                    eventSource.close();
                    currentDeepResearchEventSource = null;
                    loadingState.classList.remove('active');
                    setProcessingState(false); // Bug #23
                    alert('Deep Research 連線錯誤');
                };

            } catch (error) {
                console.error('Deep Research error:', error);
                currentDeepResearchEventSource = null;
                loadingState.classList.remove('active');
                setProcessingState(false); // Bug #23
                alert('Deep Research 發生錯誤: ' + error.message);
            }
        }

        // Helper function to convert citation numbers [1] to clickable links
        // Stage 5: Also handles URN sources (urn:llm:knowledge:xxx) with special styling
        function addCitationLinks(htmlContent, sources) {
            if (!sources || sources.length === 0) {
                return htmlContent;
            }

            // Replace [1], [2], etc. with clickable links (handles both single [1] and consecutive [3][4][23])
            return htmlContent.replace(/\[(\d+)\]/g, (match, num) => {
                const index = parseInt(num) - 1;
                if (index >= 0 && index < sources.length) {
                    const url = sources[index];
                    if (url) {  // Only create link if URL is not empty
                        // Stage 5: Check if this is a URN (LLM Knowledge source)
                        if (url.startsWith('urn:llm:knowledge:')) {
                            // Extract topic from URN for display
                            const topic = url.replace('urn:llm:knowledge:', '');
                            return `<span class="citation-urn" title="AI 背景知識：${topic}">[${num}]<sup>AI</sup></span>`;
                        }
                        // Bug #13: Handle private:// protocol (user-uploaded documents)
                        if (url.startsWith('private://')) {
                            return `<span class="citation-private" title="私人文件來源">[${num}]<sup>\u{1F4C1}</sup></span>`;
                        }
                        // Normal URL - create clickable link
                        return `<a href="${url}" target="_blank" class="citation-link" title="來源 ${num}">[${num}]</a>`;
                    }
                }
                // Bug #25 Plan C: Out-of-range citation — show styled tooltip instead of raw text
                return `<span class="citation-no-link" title="來源暫無連結">[${num}]</span>`;
            });
        }

        /**
         * Generate a citation reference list to append at the end of the report
         * @param {string[]} sources - Array of source URLs
         * @returns {string} HTML string with the reference list
         */
        function generateCitationReferenceList(sources) {
            if (!sources || sources.length === 0) {
                return '';
            }

            // Filter out empty URLs and count valid references
            const validSources = sources.map((url, index) => ({
                index: index + 1,
                url: url || ''
            })).filter(item => item.url && item.url.trim() !== '');

            if (validSources.length === 0) {
                return '';
            }

            // Collapsible toggle wrapper (default: collapsed)
            let html = '<div class="citation-reference-section">';
            html += `<button class="citation-reference-toggle" onclick="this.parentElement.classList.toggle('expanded')">
                <span class="citation-toggle-icon">▶</span>
                <span>參考資料來源 (${validSources.length})</span>
            </button>`;
            html += '<div class="citation-reference-list">';

            validSources.forEach(item => {
                const url = item.url;
                let sourceType = '新聞';
                let isClickable = true;

                if (url.startsWith('urn:llm:knowledge:')) {
                    sourceType = 'AI 背景知識';
                    isClickable = false;
                } else if (url.startsWith('private://')) {
                    sourceType = '私人文件';
                    isClickable = false;
                }

                if (isClickable) {
                    html += `<div class="citation-reference-item">
                        <span class="citation-reference-number">[${item.index}]</span>
                        <a href="${escapeHTML(url)}" target="_blank" class="citation-reference-link">
                            ${escapeHTML(url)}
                        </a>
                    </div>`;
                } else {
                    const displayText = url.startsWith('urn:llm:knowledge:')
                        ? url.replace('urn:llm:knowledge:', '')
                        : url.replace('private://', '');
                    html += `<div class="citation-reference-item">
                        <span class="citation-reference-number">[${item.index}]</span>
                        <span class="citation-reference-text">
                            <span class="citation-reference-type">${sourceType}</span>
                            ${escapeHTML(displayText)}
                        </span>
                    </div>`;
                }
            });

            html += '</div></div>';
            return html;
        }

        function displayDeepResearchResults(report, metadata, savedQuery) {
            console.log('[Deep Research] Displaying results');
            console.log('[Deep Research] Metadata received:', metadata);
            console.log('[Deep Research] Sources array:', metadata?.sources);
            console.log('[Deep Research] Sources count:', metadata?.sources?.length);

            // Store report for free conversation follow-up (include argument graph for session restore)
            currentResearchReport = {
                report: report || '',
                sources: metadata?.sources || [],
                query: savedQuery || '',
                timestamp: Date.now()
            };
            console.log('[Deep Research] Stored report for follow-up:', currentResearchReport.report.substring(0, 100) + '...');

            // Extract schema_object from content (Deep Research sends results in content array)
            let schemaObj = null;
            console.log('[Deep Research] metadata.content:', metadata?.content);
            if (metadata?.content && Array.isArray(metadata.content) && metadata.content.length > 0) {
                console.log('[Deep Research] First content item:', metadata.content[0]);
                schemaObj = metadata.content[0].schema_object;
                console.log('[Deep Research] Extracted schema_object:', schemaObj);
            } else {
                console.log('[Deep Research] No content array found, trying direct access');
                // Try direct access for backward compatibility
                schemaObj = metadata?.schema_object;
                console.log('[Deep Research] Direct schema_object:', schemaObj);
            }

            // Show results section
            resultsSection.classList.add('active');

            // Display Knowledge Graph if available (Phase KG)
            displayKnowledgeGraph(schemaObj?.knowledge_graph || metadata?.knowledge_graph);

            // Get research view container
            const researchViewEl = document.getElementById('researchView');
            if (!researchViewEl) {
                console.error('[Deep Research] researchView element not found!');
                return;
            }

            // Clear research view
            researchViewEl.innerHTML = '';

            // Create report container
            const reportContainer = document.createElement('div');
            reportContainer.className = 'deep-research-report';
            reportContainer.style.cssText = 'padding: 20px; max-width: 900px; margin: 0 auto;';

            // Convert markdown to HTML
            let reportHTML = marked.parse(report || '無結果');

            // Add citation links if sources are available
            if (metadata && metadata.sources && metadata.sources.length > 0) {
                console.log('[Deep Research] Adding citation links with', metadata.sources.length, 'sources');
                reportHTML = addCitationLinks(reportHTML, metadata.sources);
            } else {
                console.warn('[Deep Research] No sources available for citation links');
            }

            // Apply collapsible sections to h2 headings
            reportHTML = addCollapsibleSections(reportHTML);

            // Append citation reference list at the end of report
            if (metadata && metadata.sources && metadata.sources.length > 0) {
                reportHTML += generateCitationReferenceList(metadata.sources);
            }

            reportContainer.innerHTML = reportHTML;
            researchViewEl.appendChild(reportContainer);

            // Bind collapsible section handlers
            bindCollapsibleHandlers(researchViewEl);

            // Add toggle-all toolbar
            addToggleAllToolbar(reportContainer);

            // Display Reasoning Chain in research view (Phase 4)
            const argGraph = schemaObj?.argument_graph || metadata?.argument_graph;
            const chainAnalysis = schemaObj?.reasoning_chain_analysis || metadata?.reasoning_chain_analysis;
            displayReasoningChainInContainer(argGraph, chainAnalysis, researchViewEl);

            // Remove progress indicator
            const progressContainer = document.getElementById('reasoning-progress');
            if (progressContainer) {
                progressContainer.remove();
            }

            // Auto-switch to research tab
            const researchTab = document.querySelector('.tab[data-view="research"]');
            if (researchTab) {
                researchTab.click();
            }

            // Move search input to bottom of chat area (like Free Conversation mode)
            // This allows users to continue asking follow-up questions
            const chatInputContainer = document.getElementById('chatInputContainer');
            const searchContainer = document.getElementById('searchContainer');
            if (chatInputContainer && searchContainer) {
                chatInputContainer.appendChild(searchContainer);
                chatInputContainer.style.display = 'block';
                // Update button text and placeholder for follow-up mode
                const btnSearch = document.getElementById('btnSearch');
                const searchInput = document.getElementById('searchInput');
                if (btnSearch) btnSearch.textContent = '發送';
                if (searchInput) searchInput.placeholder = '基於報告繼續提問...';
                console.log('[Deep Research] Search input moved to bottom for follow-up questions');
            }

            console.log('[Deep Research] Results displayed successfully in research view');

            // 立即保存，防止關閉瀏覽器/刷新時丟失報告
            saveCurrentSession();
        }

        /**
         * Add collapsible sections to h2 headings
         */
        function addCollapsibleSections(html) {
            // Wrap h2 and following content into collapsible sections
            // This is a simplified approach that wraps each h2 with a section
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = html;

            const h2Elements = tempDiv.querySelectorAll('h2');
            h2Elements.forEach((h2, index) => {
                // Create content wrapper first to check if content is meaningful
                const content = document.createElement('div');
                content.className = 'research-section-content';

                // Move following siblings until next h2 or end
                let sibling = h2.nextElementSibling;
                while (sibling && sibling.tagName !== 'H2') {
                    const next = sibling.nextElementSibling;
                    content.appendChild(sibling);
                    sibling = next;
                }

                // Check if this is an empty "Finding X" section with only "完整報告" text
                const titleText = h2.textContent.trim();
                const contentText = content.textContent.trim();
                const isFindingSection = /^Finding\s*\d+/i.test(titleText);
                const isEmptyContent = contentText === '完整報告' || contentText === '' || contentText.length < 20;

                if (isFindingSection && isEmptyContent) {
                    // Skip this empty section - just remove the h2 and move on
                    h2.remove();
                    return;
                }

                // Create section wrapper
                const section = document.createElement('div');
                section.className = 'research-section';
                section.setAttribute('data-section-id', `section-${index}`);

                // Create header
                const header = document.createElement('div');
                header.className = 'research-section-header';
                header.innerHTML = `
                    <span class="collapse-icon">▼</span>
                    <span class="section-title">${h2.innerHTML}</span>
                `;

                section.appendChild(header);
                section.appendChild(content);

                // Replace h2 with section
                h2.parentNode.replaceChild(section, h2);
            });

            return tempDiv.innerHTML;
        }

        /**
         * Bind click handlers for collapsible sections
         */
        function bindCollapsibleHandlers(container) {
            container.querySelectorAll('.research-section-header').forEach(header => {
                header.addEventListener('click', () => {
                    const section = header.closest('.research-section');
                    const icon = header.querySelector('.collapse-icon');
                    const content = section.querySelector('.research-section-content');

                    section.classList.toggle('collapsed');
                    if (section.classList.contains('collapsed')) {
                        icon.textContent = '▶';
                        content.style.maxHeight = '0';
                        content.style.overflow = 'hidden';
                    } else {
                        icon.textContent = '▼';
                        content.style.maxHeight = '';
                        content.style.overflow = '';
                    }
                });
            });
        }

        /**
         * Add toggle-all toolbar before the report content
         */
        function addToggleAllToolbar(reportContainer) {
            const toolbar = document.createElement('div');
            toolbar.className = 'research-toggle-all-toolbar';

            let allCollapsed = false;
            const toggleBtn = document.createElement('button');
            toggleBtn.className = 'btn-toggle-all';
            toggleBtn.textContent = '全部折疊';

            toggleBtn.addEventListener('click', () => {
                allCollapsed = !allCollapsed;
                reportContainer.querySelectorAll('.research-section').forEach(section => {
                    const icon = section.querySelector('.collapse-icon');
                    const content = section.querySelector('.research-section-content');
                    if (allCollapsed) {
                        section.classList.add('collapsed');
                        if (icon) icon.textContent = '▶';
                        if (content) { content.style.maxHeight = '0'; content.style.overflow = 'hidden'; }
                    } else {
                        section.classList.remove('collapsed');
                        if (icon) icon.textContent = '▼';
                        if (content) { content.style.maxHeight = ''; content.style.overflow = ''; }
                    }
                });
                toggleBtn.textContent = allCollapsed ? '全部展開' : '全部折疊';
            });

            toolbar.appendChild(toggleBtn);
            reportContainer.insertBefore(toolbar, reportContainer.firstChild);
        }

        /**
         * Display reasoning chain in a specific container (for research view)
         */
        function displayReasoningChainInContainer(argumentGraph, chainAnalysis, targetContainer) {
            if (!argumentGraph || argumentGraph.length === 0) {
                console.log('[Reasoning Chain] No argument graph data for container');
                return;
            }

            // Store for sharing/verification
            currentArgumentGraph = argumentGraph;
            currentChainAnalysis = chainAnalysis;

            console.log('[Reasoning Chain] Rendering', argumentGraph.length, 'nodes in container');

            // Build node map
            const nodeMap = {};
            argumentGraph.forEach(node => {
                nodeMap[node.node_id] = node;
            });

            // Get topological order
            let orderedNodes = argumentGraph;
            if (chainAnalysis?.topological_order && chainAnalysis.topological_order.length > 0) {
                orderedNodes = chainAnalysis.topological_order
                    .map(id => nodeMap[id])
                    .filter(node => node !== undefined);
            }

            // Create collapsible container
            const container = createReasoningChainContainer(orderedNodes, chainAnalysis);

            // Render logic inconsistency warning
            if (chainAnalysis?.logic_inconsistencies > 0) {
                const warning = createLogicInconsistencyWarning(chainAnalysis.logic_inconsistencies);
                container.querySelector('.reasoning-chain-content').prepend(warning);
            }

            // Render cycle warning
            if (chainAnalysis?.has_cycles) {
                const cycleAlert = createCycleWarning(chainAnalysis.cycle_details);
                container.querySelector('.reasoning-chain-content').prepend(cycleAlert);
            }

            // Render critical nodes alert
            if (chainAnalysis?.critical_nodes?.length > 0) {
                const alert = createCriticalNodesAlert(chainAnalysis.critical_nodes, nodeMap);
                container.querySelector('.reasoning-chain-content').prepend(alert);
            }

            // Render each node
            orderedNodes.forEach((node, i) => {
                const nodeEl = renderArgumentNode(node, i + 1, nodeMap, chainAnalysis);
                container.querySelector('.reasoning-chain-content').appendChild(nodeEl);
            });

            // Setup hover interactions
            setupHoverInteractions(container, nodeMap);

            // Insert at beginning of target container
            targetContainer.insertBefore(container, targetContainer.firstChild);
        }

        // Knowledge Graph Display Functions (Phase KG Enhanced with D3.js)

        // Entity type colors for D3 visualization
        const KG_ENTITY_COLORS = {
            'person': '#3b82f6',      // blue
            'organization': '#8b5cf6', // purple
            'event': '#f59e0b',        // amber
            'location': '#10b981',     // emerald
            'metric': '#ef4444',       // red
            'technology': '#06b6d4',   // cyan
            'concept': '#6366f1',      // indigo
            'product': '#ec4899'       // pink
        };

        // Entity type labels
        const KG_TYPE_LABELS = {
            'person': '人物',
            'organization': '組織',
            'event': '事件',
            'location': '地點',
            'metric': '指標',
            'technology': '技術',
            'concept': '概念',
            'product': '產品'
        };

        // Relation type labels
        const KG_RELATION_LABELS = {
            'causes': '導致',
            'enables': '促成',
            'prevents': '阻止',
            'precedes': '先於',
            'concurrent': '同時',
            'part_of': '屬於',
            'owns': '擁有',
            'related_to': '相關'
        };

        // Global KG data store for view switching
        let currentKGData = null;
        let kgSimulation = null;

        function displayKnowledgeGraph(kg) {
            const container = document.getElementById('kgDisplayContainer');
            const graphView = document.getElementById('kgGraphView');
            const listContent = document.getElementById('kgDisplayContent');
            const empty = document.getElementById('kgDisplayEmpty');
            const metadata = document.getElementById('kgMetadata');
            const legend = document.getElementById('kgLegend');

            if (!kg || (!kg.entities || kg.entities.length === 0)) {
                container.style.display = 'none';
                console.log('[KG] No knowledge graph data to display');
                return;
            }

            // Store KG data globally
            currentKGData = kg;

            // Respect user's KG hidden preference
            if (container.dataset.userHidden === 'true') {
                const restoreBar = document.getElementById('kgRestoreBar');
                if (restoreBar) restoreBar.style.display = 'block';
                // Still render data so it's ready when user restores
            } else {
                container.style.display = 'block';
            }

            // Update metadata
            const entityCount = kg.entities?.length || 0;
            const relCount = kg.relationships?.length || 0;
            const timestamp = kg.metadata?.generated_at ? new Date(kg.metadata.generated_at).toLocaleTimeString('zh-TW', {hour: '2-digit', minute: '2-digit'}) : '';
            metadata.textContent = `${entityCount} 個實體 • ${relCount} 個關係${timestamp ? ' • 生成於 ' + timestamp : ''}`;

            // Render list view content
            renderKGListView(kg, listContent);

            // Render graph view with D3
            renderKGGraphView(kg, graphView);

            // Render legend
            renderKGLegend(kg, legend);

            // Setup view toggle
            setupKGViewToggle();

            empty.style.display = 'none';
            console.log('[KG] Knowledge graph displayed successfully with D3 visualization');
        }

        function renderKGListView(kg, container) {
            let html = '';

            // Entities section
            if (kg.entities && kg.entities.length > 0) {
                html += '<div class="kg-section">';
                html += `<div class="kg-section-title">實體 (${kg.entities.length})</div>`;
                kg.entities.forEach(entity => {
                    const typeLabel = KG_TYPE_LABELS[entity.entity_type] || entity.entity_type;
                    html += '<div class="kg-item">';
                    html += `<div><span class="kg-item-name">${escapeHTML(entity.name)}</span>`;
                    html += `<span class="kg-item-type">${typeLabel}</span>`;
                    html += `<span class="kg-item-confidence ${entity.confidence}">${entity.confidence}</span>`;
                    html += '</div>';
                    if (entity.description) {
                        html += `<div class="kg-item-desc">${escapeHTML(entity.description)}</div>`;
                    }
                    html += '</div>';
                });
                html += '</div>';
            }

            // Relationships section
            if (kg.relationships && kg.relationships.length > 0) {
                html += '<div class="kg-section">';
                html += `<div class="kg-section-title">關係 (${kg.relationships.length})</div>`;

                const entityMap = {};
                if (kg.entities) {
                    kg.entities.forEach(e => entityMap[e.entity_id] = e.name);
                }

                kg.relationships.forEach(rel => {
                    const relationLabel = KG_RELATION_LABELS[rel.relation_type] || rel.relation_type;
                    const sourceName = entityMap[rel.source_entity_id] || '未知';
                    const targetName = entityMap[rel.target_entity_id] || '未知';

                    html += '<div class="kg-item">';
                    html += `<div>${escapeHTML(sourceName)} <span class="kg-relationship-arrow">→</span> ${escapeHTML(targetName)}`;
                    html += `<span class="kg-item-type">${relationLabel}</span>`;
                    html += `<span class="kg-item-confidence ${rel.confidence}">${rel.confidence}</span>`;
                    html += '</div>';
                    if (rel.description) {
                        html += `<div class="kg-item-desc">${escapeHTML(rel.description)}</div>`;
                    }
                    html += '</div>';
                });
                html += '</div>';
            }

            container.innerHTML = html;
        }

        function renderKGGraphView(kg, container) {
            // Clear previous SVG
            d3.select(container).select('svg').remove();

            // Preserve tooltip
            const tooltip = document.getElementById('kgTooltip');

            const width = container.clientWidth || 600;
            const height = container.clientHeight || 400;

            // Create SVG
            const svg = d3.select(container)
                .append('svg')
                .attr('width', width)
                .attr('height', height);

            // Add zoom behavior
            const g = svg.append('g');
            const zoom = d3.zoom()
                .scaleExtent([0.3, 3])
                .on('zoom', (event) => {
                    g.attr('transform', event.transform);
                });
            svg.call(zoom);

            // Build entity map
            const entityMap = {};
            kg.entities.forEach(e => entityMap[e.entity_id] = e);

            // Prepare nodes and links for D3
            const nodes = kg.entities.map(e => ({
                id: e.entity_id,
                name: e.name,
                type: e.entity_type,
                description: e.description,
                confidence: e.confidence
            }));

            const nodeIds = new Set(nodes.map(n => n.id));
            const links = (kg.relationships || [])
                .filter(r => nodeIds.has(r.source_entity_id) && nodeIds.has(r.target_entity_id))
                .map(r => ({
                    source: r.source_entity_id,
                    target: r.target_entity_id,
                    type: r.relation_type,
                    description: r.description,
                    confidence: r.confidence
                }));

            // Create force simulation
            if (kgSimulation) {
                kgSimulation.stop();
            }

            kgSimulation = d3.forceSimulation(nodes)
                .force('link', d3.forceLink(links).id(d => d.id).distance(120))
                .force('charge', d3.forceManyBody().strength(-300))
                .force('center', d3.forceCenter(width / 2, height / 2))
                .force('collision', d3.forceCollide().radius(40));

            // Draw arrow markers for directed edges
            svg.append('defs').selectAll('marker')
                .data(['arrow'])
                .enter().append('marker')
                .attr('id', 'arrow')
                .attr('viewBox', '0 -5 10 10')
                .attr('refX', 25)
                .attr('refY', 0)
                .attr('markerWidth', 6)
                .attr('markerHeight', 6)
                .attr('orient', 'auto')
                .append('path')
                .attr('fill', '#94a3b8')
                .attr('d', 'M0,-5L10,0L0,5');

            // Draw links
            const link = g.append('g')
                .selectAll('line')
                .data(links)
                .enter().append('line')
                .attr('class', 'kg-link')
                .attr('stroke', '#94a3b8')
                .attr('stroke-width', 2)
                .attr('marker-end', 'url(#arrow)');

            // Draw link labels
            const linkLabel = g.append('g')
                .selectAll('text')
                .data(links)
                .enter().append('text')
                .attr('class', 'kg-link-label')
                .text(d => KG_RELATION_LABELS[d.type] || d.type);

            // Draw nodes
            const node = g.append('g')
                .selectAll('g')
                .data(nodes)
                .enter().append('g')
                .attr('class', 'kg-node')
                .call(d3.drag()
                    .on('start', dragStarted)
                    .on('drag', dragged)
                    .on('end', dragEnded));

            // Node circles
            node.append('circle')
                .attr('r', 18)
                .attr('fill', d => KG_ENTITY_COLORS[d.type] || '#6b7280');

            // Node labels
            node.append('text')
                .attr('dy', 30)
                .text(d => d.name.length > 10 ? d.name.substring(0, 10) + '...' : d.name);

            // Node hover effects
            node.on('mouseenter', function(event, d) {
                // Highlight connected links
                link.attr('stroke', l => (l.source.id === d.id || l.target.id === d.id) ? '#3b82f6' : '#94a3b8')
                    .attr('stroke-width', l => (l.source.id === d.id || l.target.id === d.id) ? 3 : 2);

                // Show tooltip
                const typeLabel = KG_TYPE_LABELS[d.type] || d.type;
                tooltip.innerHTML = `
                    <div class="kg-tooltip-title">${escapeHTML(d.name)}</div>
                    <div class="kg-tooltip-type">${typeLabel}</div>
                    ${d.description ? `<div class="kg-tooltip-desc">${escapeHTML(d.description)}</div>` : ''}
                `;
                tooltip.classList.add('visible');
                tooltip.style.left = (event.offsetX + 15) + 'px';
                tooltip.style.top = (event.offsetY - 10) + 'px';
            })
            .on('mousemove', function(event) {
                tooltip.style.left = (event.offsetX + 15) + 'px';
                tooltip.style.top = (event.offsetY - 10) + 'px';
            })
            .on('mouseleave', function() {
                link.attr('stroke', '#94a3b8').attr('stroke-width', 2);
                tooltip.classList.remove('visible');
            });

            // Update positions on tick
            kgSimulation.on('tick', () => {
                link
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);

                linkLabel
                    .attr('x', d => (d.source.x + d.target.x) / 2)
                    .attr('y', d => (d.source.y + d.target.y) / 2);

                node.attr('transform', d => `translate(${d.x},${d.y})`);
            });

            // Drag functions
            function dragStarted(event, d) {
                if (!event.active) kgSimulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            }

            function dragged(event, d) {
                d.fx = event.x;
                d.fy = event.y;
            }

            function dragEnded(event, d) {
                if (!event.active) kgSimulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            }
        }

        function renderKGLegend(kg, container) {
            // Get unique entity types
            const types = [...new Set(kg.entities.map(e => e.entity_type))];

            let html = '';
            types.forEach(type => {
                const color = KG_ENTITY_COLORS[type] || '#6b7280';
                const label = KG_TYPE_LABELS[type] || type;
                html += `
                    <div class="kg-legend-item">
                        <div class="kg-legend-color" style="background: ${color};"></div>
                        <span>${label}</span>
                    </div>
                `;
            });

            container.innerHTML = html;
        }

        function setupKGViewToggle() {
            const toggleContainer = document.getElementById('kgViewToggle');
            const graphView = document.getElementById('kgGraphView');
            const listView = document.getElementById('kgDisplayContent');

            if (!toggleContainer) return;

            toggleContainer.querySelectorAll('.kg-view-btn').forEach(btn => {
                btn.addEventListener('click', function() {
                    const view = this.getAttribute('data-view');

                    // Update button states
                    toggleContainer.querySelectorAll('.kg-view-btn').forEach(b => b.classList.remove('active'));
                    this.classList.add('active');

                    // Toggle views
                    if (view === 'graph') {
                        graphView.style.display = 'block';
                        listView.style.display = 'none';
                        // Re-render graph if needed (handles resize)
                        if (currentKGData && graphView.clientWidth > 0) {
                            renderKGGraphView(currentKGData, graphView);
                        }
                    } else {
                        graphView.style.display = 'none';
                        listView.style.display = 'block';
                    }

                    console.log('[KG] Switched to', view, 'view');
                });
            });
        }

        // ============================================================
        // Reasoning Chain Visualization (Phase 4 - Enhanced)
        // ============================================================

        /**
         * Display reasoning chain with dependency tracking
         */
        function displayReasoningChain(argumentGraph, chainAnalysis) {
            console.log('[Reasoning Chain] Called with:', argumentGraph, chainAnalysis);

            if (!argumentGraph || argumentGraph.length === 0) {
                console.log('[Reasoning Chain] No argument graph data, skipping render');
                return;
            }

            // Store for sharing/verification
            currentArgumentGraph = argumentGraph;
            currentChainAnalysis = chainAnalysis;

            console.log('[Reasoning Chain] Rendering', argumentGraph.length, 'nodes');

            // Build node map
            const nodeMap = {};
            argumentGraph.forEach(node => {
                nodeMap[node.node_id] = node;
            });

            // Get topological order
            let orderedNodes = argumentGraph;
            if (chainAnalysis?.topological_order && chainAnalysis.topological_order.length > 0) {
                orderedNodes = chainAnalysis.topological_order
                    .map(id => nodeMap[id])
                    .filter(node => node !== undefined);
                console.log('[Reasoning Chain] Using topological order for rendering');
            }

            // Create collapsible container
            const container = createReasoningChainContainer(orderedNodes, chainAnalysis);

            // Render logic inconsistency warning
            if (chainAnalysis?.logic_inconsistencies > 0) {
                const warning = createLogicInconsistencyWarning(chainAnalysis.logic_inconsistencies);
                container.querySelector('.reasoning-chain-content').prepend(warning);
            }

            // Render cycle warning
            if (chainAnalysis?.has_cycles) {
                const cycleAlert = createCycleWarning(chainAnalysis.cycle_details);
                container.querySelector('.reasoning-chain-content').prepend(cycleAlert);
            }

            // Render critical nodes alert
            if (chainAnalysis?.critical_nodes?.length > 0) {
                const alert = createCriticalNodesAlert(chainAnalysis.critical_nodes, nodeMap);
                container.querySelector('.reasoning-chain-content').prepend(alert);
            }

            // Render each node (with hover effects)
            orderedNodes.forEach((node, i) => {
                const nodeEl = renderArgumentNode(node, i + 1, nodeMap, chainAnalysis);
                container.querySelector('.reasoning-chain-content').appendChild(nodeEl);
            });

            // Setup hover interactions
            setupHoverInteractions(container, nodeMap);

            // Insert before report
            const listView = document.getElementById('listView');
            const reportContainer = listView.querySelector('.deep-research-report');
            if (reportContainer) {
                listView.insertBefore(container, reportContainer);
            } else {
                listView.appendChild(container);
            }
        }

        /**
         * Create container with header and toggle
         */
        function createReasoningChainContainer(nodes, chainAnalysis) {
            const container = document.createElement('div');
            container.className = 'reasoning-chain-container';
            container.style.cssText = `
                background: #f8f9fa;
                border-left: 4px solid #6366f1;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 24px;
                max-width: 900px;
                margin-left: auto;
                margin-right: auto;
            `;

            const header = document.createElement('div');
            header.style.cssText = 'display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; cursor: pointer;';
            header.innerHTML = `
                <div style="font-size: 18px; font-weight: 700; color: #1a1a1a;">
                    🧠 推論過程
                    <span style="color: #666; font-size: 14px; font-weight: 400;">
                        (${nodes.length} 個推論步驟${chainAnalysis?.max_depth !== undefined ? `, 深度 ${chainAnalysis.max_depth}` : ''})
                    </span>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <button class="btn-share-reasoning" style="background: white; border: 1px solid #ddd; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 13px; transition: all 0.2s;">
                        🔗 給其他 AI 驗證
                    </button>
                    <button class="btn-toggle-chain" style="background: white; border: 1px solid #ddd; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 13px;">
                        展開
                    </button>
                </div>
            `;

            const content = document.createElement('div');
            content.className = 'reasoning-chain-content';
            content.style.display = 'none';

            // Toggle functionality
            const toggleBtn = header.querySelector('.btn-toggle-chain');
            header.addEventListener('click', (e) => {
                // Don't toggle if clicking the share button
                if (e.target.closest('.btn-share-reasoning')) return;
                const isHidden = content.style.display === 'none';
                content.style.display = isHidden ? 'block' : 'none';
                toggleBtn.textContent = isHidden ? '收起' : '展開';
            });

            // Share reasoning button
            const shareBtn = header.querySelector('.btn-share-reasoning');
            shareBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // Don't trigger toggle
                shareContentOverride = formatReasoningForVerification();
                modalOverlay.classList.add('active');
            });

            container.appendChild(header);
            container.appendChild(content);

            return container;
        }

        /**
         * Create logic inconsistency warning
         */
        function createLogicInconsistencyWarning(count) {
            const alert = document.createElement('div');
            alert.style.cssText = `
                background: #fef3c7;
                border-left: 4px solid #f59e0b;
                padding: 12px 16px;
                border-radius: 6px;
                margin-bottom: 16px;
            `;
            alert.innerHTML = `
                <div style="font-weight: 700; color: #92400e; margin-bottom: 4px;">⚠️ 邏輯一致性問題</div>
                <div style="color: #78350f; font-size: 13px;">
                    偵測到 ${count} 個推論步驟的信心度可能高於其前提（邏輯膨脹）。請檢視帶有 ⚠️ 標記的推論步驟。
                </div>
            `;
            return alert;
        }

        /**
         * Create cycle warning
         */
        function createCycleWarning(cycleDetails) {
            const alert = document.createElement('div');
            alert.style.cssText = `
                background: #fee2e2;
                border-left: 4px solid #dc2626;
                padding: 12px 16px;
                border-radius: 6px;
                margin-bottom: 16px;
            `;
            alert.innerHTML = `
                <div style="font-weight: 700; color: #991b1b; margin-bottom: 4px;">⚠️ 檢測到循環依賴</div>
                <div style="color: #7f1d1d; font-size: 13px;">${cycleDetails || '推論鏈存在循環引用，可能影響可靠性'}</div>
            `;
            return alert;
        }

        /**
         * Create critical nodes alert
         */
        function createCriticalNodesAlert(criticalNodes, nodeMap) {
            const alert = document.createElement('div');
            alert.style.cssText = `
                background: #fef3c7;
                border-left: 4px solid #f59e0b;
                padding: 12px 16px;
                border-radius: 6px;
                margin-bottom: 16px;
            `;

            const criticalHtml = criticalNodes.map(critical => {
                const node = nodeMap[critical.node_id];
                if (!node) return '';
                return `
                    <div style="margin-bottom: 8px; color: #78350f;">
                        <strong>「${node.claim.substring(0, 50)}${node.claim.length > 50 ? '...' : ''}」</strong>
                        影響 ${critical.affects_count} 個後續推論
                        ${critical.criticality_reason ? `<br><span style="font-size: 13px;">└─ ${critical.criticality_reason}</span>` : ''}
                    </div>
                `;
            }).join('');

            alert.innerHTML = `
                <div style="font-weight: 700; color: #92400e; margin-bottom: 8px;">🚨 關鍵薄弱環節</div>
                ${criticalHtml}
            `;

            return alert;
        }

        /**
         * Render single argument node with full details
         */
        function renderArgumentNode(node, stepNumber, nodeMap, chainAnalysis) {
            const nodeEl = document.createElement('div');
            nodeEl.className = 'argument-node';
            nodeEl.id = `node-${node.node_id}`;
            nodeEl.setAttribute('data-node-id', node.node_id);
            nodeEl.setAttribute('data-depends', JSON.stringify(node.depends_on || []));

            // Find nodes that depend on this one (for hover highlight)
            const affectedIds = [];
            Object.values(nodeMap).forEach(n => {
                if (n.depends_on && n.depends_on.includes(node.node_id)) {
                    affectedIds.push(n.node_id);
                }
            });
            nodeEl.setAttribute('data-affects', JSON.stringify(affectedIds));

            nodeEl.style.cssText = `
                background: white;
                border: 2px solid #e5e7eb;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 12px;
                transition: all 0.2s ease;
            `;

            const emoji = {deduction: '🔷', induction: '🔶', abduction: '🔸'}[node.reasoning_type] || '💭';
            const label = {deduction: '演繹', induction: '歸納', abduction: '溯因'}[node.reasoning_type];
            const score = node.confidence_score ?? inferScore(node.confidence);
            const scoreColor = score >= 7 ? '#16a34a' : score >= 4 ? '#f59e0b' : '#dc2626';

            // Get impact info
            let impactInfo = '';
            if (chainAnalysis?.critical_nodes) {
                const critical = chainAnalysis.critical_nodes.find(c => c.node_id === node.node_id);
                if (critical && critical.affects_count > 0) {
                    impactInfo = `<div style="color: #dc2626; font-size: 13px; margin-top: 8px;">
                        ⚡ 影響 ${critical.affects_count} 個後續推論
                    </div>`;
                }
            }

            // Logic warnings
            let warningsHtml = '';
            if (node.logic_warnings && node.logic_warnings.length > 0) {
                warningsHtml = node.logic_warnings.map(w => `
                    <div style="color: #f59e0b; font-size: 13px; margin-top: 4px;">
                        ⚠️ ${w}
                    </div>
                `).join('');
            }

            // Render dependencies
            let depsHtml = '';
            if (node.depends_on && node.depends_on.length > 0) {
                const depLabels = node.depends_on.map(depId => {
                    const depIndex = Object.keys(nodeMap).indexOf(depId) + 1;
                    return `步驟 ${depIndex}`;
                });
                depsHtml = `<div style="color: #6366f1; font-size: 13px; margin-top: 8px;">
                    ↑ 依賴：${depLabels.join(', ')}
                </div>`;
            }

            // Evidence
            const evidenceHtml = node.evidence_ids && node.evidence_ids.length > 0
                ? `<div style="color: #666; font-size: 13px; margin-top: 4px;">
                       證據來源：${node.evidence_ids.map(id => `<span style="background: #e5e7eb; padding: 2px 6px; border-radius: 3px; margin-right: 4px;">[${id}]</span>`).join('')}
                   </div>`
                : '<div style="color: #999; font-size: 13px; margin-top: 4px;">無直接證據引用</div>';

            nodeEl.innerHTML = `
                <div style="font-weight: 700; margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                    <span style="background: #f3f4f6; padding: 4px 8px; border-radius: 4px; font-size: 14px;">[${stepNumber}]</span>
                    <span>${emoji} ${label}</span>
                    <span style="color: ${scoreColor}; font-size: 14px; background: ${scoreColor}22; padding: 2px 8px; border-radius: 4px;">
                        信心度 ${score.toFixed(1)}/10
                    </span>
                </div>
                <div style="color: #1a1a1a; margin-bottom: 8px; line-height: 1.6;">「${node.claim}」</div>
                ${evidenceHtml}
                ${depsHtml}
                ${impactInfo}
                ${warningsHtml}
            `;

            return nodeEl;
        }

        /**
         * Setup hover interactions
         */
        function setupHoverInteractions(container, nodeMap) {
            const nodes = container.querySelectorAll('.argument-node');

            nodes.forEach(nodeEl => {
                nodeEl.addEventListener('mouseenter', () => {
                    const nodeId = nodeEl.getAttribute('data-node-id');
                    const dependsOn = JSON.parse(nodeEl.getAttribute('data-depends') || '[]');
                    const affects = JSON.parse(nodeEl.getAttribute('data-affects') || '[]');

                    // Highlight current node
                    nodeEl.style.borderColor = '#6366f1';
                    nodeEl.style.boxShadow = '0 4px 12px rgba(99, 102, 241, 0.2)';

                    // Highlight dependencies (parents) - blue background
                    dependsOn.forEach(depId => {
                        const depEl = document.getElementById(`node-${depId}`);
                        if (depEl) {
                            depEl.style.backgroundColor = '#dbeafe';
                            depEl.style.borderColor = '#3b82f6';
                        }
                    });

                    // Highlight affected nodes (children) - red border
                    affects.forEach(affectedId => {
                        const affectedEl = document.getElementById(`node-${affectedId}`);
                        if (affectedEl) {
                            affectedEl.style.borderColor = '#ef4444';
                            affectedEl.style.borderWidth = '2px';
                        }
                    });
                });

                nodeEl.addEventListener('mouseleave', () => {
                    // Reset all highlights
                    nodes.forEach(n => {
                        n.style.backgroundColor = 'white';
                        n.style.borderColor = '#e5e7eb';
                        n.style.borderWidth = '2px';
                        n.style.boxShadow = 'none';
                    });
                });
            });
        }

        /**
         * Infer numerical score from confidence level
         */
        function inferScore(confidence) {
            const mapping = { 'high': 8.0, 'medium': 5.0, 'low': 2.0 };
            return mapping[confidence] || 5.0;
        }

        /**
         * Format reasoning chain for AI verification
         */
        function formatReasoningForVerification() {
            if (!currentArgumentGraph || currentArgumentGraph.length === 0) {
                return '無推論鏈資料可供驗證。';
            }

            const query = currentResearchReport?.query || conversationHistory[0] || '(未知查詢)';
            let content = '';

            // Opening prompt
            content += `我請其他 Agent 做「${query}」的研究，他的推論過程如下，請幫我檢查是否合理：\n\n`;
            content += `${'='.repeat(50)}\n\n`;

            // Reasoning steps
            content += `【推論步驟】（共 ${currentArgumentGraph.length} 步）\n\n`;

            currentArgumentGraph.forEach((node, index) => {
                const typeLabel = {deduction: '演繹', induction: '歸納', abduction: '溯因'}[node.reasoning_type] || node.reasoning_type;
                const score = node.confidence_score ?? inferScore(node.confidence);

                content += `步驟 ${index + 1}：${typeLabel}\n`;
                content += `主張：「${node.claim}」\n`;
                content += `信心度：${score.toFixed(1)}/10\n`;

                if (node.evidence_ids && node.evidence_ids.length > 0) {
                    content += `證據來源：[${node.evidence_ids.join('], [')}]\n`;
                } else {
                    content += `證據來源：無直接引用\n`;
                }

                if (node.depends_on && node.depends_on.length > 0) {
                    const depLabels = node.depends_on.map(depId => {
                        const depIndex = currentArgumentGraph.findIndex(n => n.node_id === depId);
                        return depIndex >= 0 ? `步驟 ${depIndex + 1}` : depId;
                    });
                    content += `依賴：${depLabels.join(', ')}\n`;
                }

                if (node.logic_warnings && node.logic_warnings.length > 0) {
                    content += `警告：${node.logic_warnings.join('; ')}\n`;
                }

                content += `\n`;
            });

            // Analysis summary
            if (currentChainAnalysis) {
                content += `${'='.repeat(50)}\n\n`;
                content += `【分析摘要】\n`;
                content += `- 推論步驟數：${currentArgumentGraph.length}\n`;
                if (currentChainAnalysis.max_depth !== undefined) {
                    content += `- 推論深度：${currentChainAnalysis.max_depth}\n`;
                }
                if (currentChainAnalysis.logic_inconsistencies > 0) {
                    content += `- 邏輯不一致數：${currentChainAnalysis.logic_inconsistencies}\n`;
                }
                if (currentChainAnalysis.has_cycles) {
                    content += `- 存在循環依賴\n`;
                }
                if (currentChainAnalysis.critical_nodes?.length > 0) {
                    content += `- 關鍵薄弱環節：${currentChainAnalysis.critical_nodes.length} 個\n`;
                }
            }

            content += `\n${'='.repeat(50)}\n`;
            content += `\n請檢查上述推論鏈的邏輯是否正確、證據是否充分、結論是否合理。`;

            return content;
        }

        // KG Toggle Button Handler (Bug #17: operate on kgContentWrapper, not individual elements)
        document.addEventListener('DOMContentLoaded', () => {
            const toggleButton = document.getElementById('kgToggleButton');
            const wrapper = document.getElementById('kgContentWrapper');
            const icon = document.getElementById('kgToggleIcon');

            if (toggleButton && wrapper) {
                toggleButton.addEventListener('click', () => {
                    const isCollapsed = wrapper.style.display === 'none';
                    wrapper.style.display = isCollapsed ? '' : 'none';
                    icon.textContent = isCollapsed ? '▼' : '▶';
                    toggleButton.childNodes[1].textContent = isCollapsed ? ' 收起' : ' 展開';
                });
            }
        });

        // Free Conversation Mode function - uses POST + fetch streaming for large payloads
        async function performFreeConversation(query) {
            // Add user message to chat
            addChatMessage('user', query);

            // Save session immediately on query submit (before waiting for response)
            saveCurrentSession();

            // Clear input
            searchInput.value = '';

            // Show typing indicator in chat flow
            const typingDiv = document.createElement('div');
            typingDiv.className = 'chat-message assistant';
            typingDiv.id = 'chatTypingIndicator';
            typingDiv.innerHTML = `
                <div class="chat-message-header">AI 助理</div>
                <div class="chat-message-bubble">
                    <div class="chat-typing-indicator">
                        <div class="dot"></div>
                        <div class="dot"></div>
                        <div class="dot"></div>
                    </div>
                </div>
            `;
            chatMessagesEl.appendChild(typingDiv);
            chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;

            try {
                const base = window.location.origin;

                // Build conversation context
                const searchQueries = conversationHistory.slice();
                const recentChatHistory = chatHistory.slice(-4);
                const chatQueries = recentChatHistory.filter(msg => msg.role === 'user').map(msg => msg.content);
                const allPrevQueries = [...searchQueries, ...chatQueries];

                // Reference context for UI display
                let referenceContext = '';
                if (accumulatedArticles.length > 0) {
                    referenceContext = `參考資料：基於 ${accumulatedArticles.length} 則新聞（來自 ${conversationHistory.length} 次搜尋）`;
                }

                console.log('=== Free Conversation Debug ===');
                console.log('Current query:', query);
                console.log('All prev queries being sent:', allPrevQueries);
                if (currentResearchReport) {
                    console.log('Research report length:', currentResearchReport.report?.length || 0);
                }

                // Build POST body - can handle unlimited size
                const requestBody = {
                    query: query,
                    site: 'all',
                    generate_mode: 'generate',
                    streaming: true,
                    free_conversation: true,
                    session_id: currentSessionId,
                    conversation_id: currentConversationId || '',
                    prev: allPrevQueries
                };

                // Add full research report if available (no truncation needed with POST)
                if (currentResearchReport && currentResearchReport.report) {
                    requestBody.research_report = currentResearchReport.report;
                    console.log('[Free Conversation] Passing full research report:', currentResearchReport.report.length, 'chars');
                }

                // Add pinned articles if any
                if (pinnedNewsCards.length > 0) {
                    requestBody.pinned_articles = pinnedNewsCards.map(p => ({
                        url: p.url, title: p.title, description: p.description || ''
                    }));
                }

                // Add private sources parameters if enabled
                if (includePrivateSources) {
                    requestBody.include_private_sources = true;
                    requestBody.user_id = TEMP_USER_ID;
                }

                console.log('[Free Conversation] Using POST request with body size:', JSON.stringify(requestBody).length, 'bytes');

                // Bug #23: Cancel any previous active requests and create abort controller
                cancelAllActiveRequests();
                currentFreeConvAbortController = new AbortController();
                setProcessingState(true);

                // Use fetch with POST for streaming (handles large payloads)
                let chatData = await handlePostStreamingRequest('/ask', requestBody, query, currentFreeConvAbortController.signal);
                currentFreeConvAbortController = null;

                // Remove typing indicator
                const typingEl = document.getElementById('chatTypingIndicator');
                if (typingEl) typingEl.remove();

                // Add assistant response to chat
                if (chatData.answer) {
                    addChatMessage('assistant', chatData.answer, referenceContext);
                } else {
                    addChatMessage('assistant', '抱歉，我無法回答這個問題。');
                }
                setProcessingState(false); // Bug #23
                chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;

                // 自動建立/更新 session
                saveCurrentSession();
            } catch (error) {
                currentFreeConvAbortController = null;
                setProcessingState(false); // Bug #23
                // Remove typing indicator on error
                const typingElErr = document.getElementById('chatTypingIndicator');
                if (typingElErr) typingElErr.remove();

                if (error.name === 'AbortError') {
                    console.log('[Free Conversation] Request aborted by user');
                    return;
                }
                console.error('Chat failed:', error);
                addChatMessage('assistant', '抱歉，發生錯誤。請稍後再試。');
            }
        }

        // Add message to chat UI
        function addChatMessage(role, content, referenceInfo = null, existingMsgId = null) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `chat-message ${role}`;

            // Assign unique ID to message
            const msgId = existingMsgId || `msg-${Date.now()}-${messageIdCounter++}`;
            messageDiv.setAttribute('data-msg-id', msgId);

            const headerText = role === 'user' ? '你' : 'AI 助理';

            // For assistant messages, use marked.js for full Markdown rendering
            // For user messages, escape HTML for safety
            let formattedContent = content;
            if (role === 'assistant') {
                formattedContent = marked.parse(content);
            } else {
                formattedContent = escapeHTML(content);
            }

            // Check if this message is already pinned
            const isPinned = pinnedMessages.some(p => p.msgId === msgId);

            let messageHTML = `
                <div class="chat-message-header">${headerText}</div>
                <div class="chat-message-content-wrapper">
                    <div class="chat-message-bubble">${formattedContent}</div>
                    <button class="chat-message-pin ${isPinned ? 'pinned' : ''}" data-msg-id="${msgId}" title="${isPinned ? '取消釘選' : '釘選訊息'}">📌</button>
                </div>
            `;

            if (referenceInfo && role === 'assistant') {
                messageHTML += `<div class="chat-reference-info">📚 ${referenceInfo}</div>`;
            }

            messageDiv.innerHTML = messageHTML;
            chatMessagesEl.appendChild(messageDiv);

            // Add click handler for pin button
            const pinBtn = messageDiv.querySelector('.chat-message-pin');
            pinBtn.addEventListener('click', () => togglePinMessage(msgId, content, role));

            // Store in chat history with ID
            chatHistory.push({ role, content, timestamp: Date.now(), msgId });

            // Scroll to bottom
            chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;

            return msgId;
        }

        // ==================== PIN MESSAGE FUNCTIONS ====================

        // Toggle pin state for a message
        function togglePinMessage(msgId, content, role) {
            const existingIndex = pinnedMessages.findIndex(p => p.msgId === msgId);

            if (existingIndex !== -1) {
                // Unpin
                pinnedMessages.splice(existingIndex, 1);
                console.log('[Pin] Unpinned message:', msgId);
            } else {
                // Pin - enforce max limit
                if (pinnedMessages.length >= MAX_PINNED_MESSAGES) {
                    // Remove oldest pinned message
                    pinnedMessages.shift();
                }
                pinnedMessages.push({
                    msgId,
                    content,
                    role,
                    pinnedAt: Date.now()
                });
                console.log('[Pin] Pinned message:', msgId);
            }

            // Update pin button state
            updatePinButtonState(msgId);

            // Render the banner
            renderPinnedBanner();

            // 只在 session 已存在時才存檔（釘選不應建立新 session）
            if (currentLoadedSessionId !== null) {
                saveCurrentSession();
            }
        }

        // Update the visual state of a pin button
        function updatePinButtonState(msgId) {
            const isPinned = pinnedMessages.some(p => p.msgId === msgId);
            const messageEl = document.querySelector(`[data-msg-id="${msgId}"]`);
            if (messageEl) {
                const pinBtn = messageEl.querySelector('.chat-message-pin');
                if (pinBtn) {
                    pinBtn.classList.toggle('pinned', isPinned);
                    pinBtn.title = isPinned ? '取消釘選' : '釘選訊息';
                }
            }
        }

        // Render the pinned messages banner
        function renderPinnedBanner() {
            const banner = document.getElementById('pinnedBanner');
            const bannerText = document.getElementById('pinnedBannerText');
            const bannerCount = document.getElementById('pinnedBannerCount');
            const bannerToggle = document.getElementById('pinnedBannerToggle');
            const bannerDropdown = document.getElementById('pinnedBannerDropdown');

            if (!banner) return;

            if (pinnedMessages.length === 0) {
                banner.style.display = 'none';
                return;
            }

            banner.style.display = 'block';

            // Show the latest pinned message
            const latestPinned = pinnedMessages[pinnedMessages.length - 1];
            const truncatedText = truncateText(latestPinned.content, 50);
            bannerText.textContent = truncatedText;

            // Update count
            bannerCount.textContent = pinnedMessages.length;
            bannerToggle.style.display = pinnedMessages.length > 1 ? 'flex' : 'none';

            // Render dropdown items
            bannerDropdown.innerHTML = '';
            pinnedMessages.slice().reverse().forEach((pinned, idx) => {
                const item = document.createElement('div');
                item.className = 'pinned-dropdown-item';

                const roleLabel = pinned.role === 'user' ? '你' : 'AI';
                const truncated = truncateText(pinned.content, 40);

                item.innerHTML = `
                    <span class="pinned-dropdown-role">${roleLabel}：</span>
                    <span class="pinned-dropdown-text">${escapeHTML(truncated)}</span>
                    <button class="pinned-dropdown-unpin" data-msg-id="${pinned.msgId}" title="取消釘選">✕</button>
                `;

                // Click to scroll to message (dropdown stays open)
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (!e.target.classList.contains('pinned-dropdown-unpin')) {
                        console.log('[Pin] Scrolling to message:', pinned.msgId);
                        scrollToMessage(pinned.msgId);
                        // Don't close dropdown - user can close manually
                    }
                });

                // Unpin button
                const unpinBtn = item.querySelector('.pinned-dropdown-unpin');
                unpinBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    togglePinMessage(pinned.msgId, pinned.content, pinned.role);
                });

                bannerDropdown.appendChild(item);
            });
        }

        // Truncate text to specified length
        function truncateText(text, maxLength) {
            // Get first line only
            const firstLine = text.split('\n')[0];
            if (firstLine.length <= maxLength) return firstLine;
            return firstLine.substring(0, maxLength) + '...';
        }

        // Scroll to a specific message (only scroll chat container, not the page)
        function scrollToMessage(msgId) {
            console.log('[Pin] Looking for message:', msgId);
            // Use specific selector to find chat-message div, not dropdown buttons
            const messageEl = document.querySelector(`.chat-message[data-msg-id="${msgId}"]`);
            const chatContainer = document.getElementById('chatMessages');
            console.log('[Pin] Found element:', messageEl);

            if (messageEl && chatContainer) {
                // Calculate scroll position within the chat container
                const containerRect = chatContainer.getBoundingClientRect();
                const messageRect = messageEl.getBoundingClientRect();
                const scrollOffset = messageRect.top - containerRect.top + chatContainer.scrollTop;

                // Smooth scroll only the chat container
                chatContainer.scrollTo({
                    top: scrollOffset,
                    behavior: 'smooth'
                });

                // Highlight briefly
                messageEl.classList.add('highlight');
                setTimeout(() => messageEl.classList.remove('highlight'), 2000);
            } else {
                console.warn('[Pin] Message element not found for id:', msgId);
            }
        }

        // Toggle pinned dropdown visibility
        function togglePinnedDropdown() {
            console.log('[Pin] Toggling dropdown');
            const dropdown = document.getElementById('pinnedBannerDropdown');
            const arrow = document.querySelector('.pinned-banner-arrow');
            if (dropdown) {
                const isVisible = dropdown.classList.toggle('visible');
                if (arrow) {
                    arrow.textContent = isVisible ? '▲' : '▼';
                }
            }
        }

        // Close pinned dropdown
        function closePinnedDropdown() {
            const dropdown = document.getElementById('pinnedBannerDropdown');
            const arrow = document.querySelector('.pinned-banner-arrow');
            if (dropdown) {
                dropdown.classList.remove('visible');
                if (arrow) arrow.textContent = '▼';
            }
        }

        // Initialize pinned banner event listeners
        function initPinnedBanner() {
            console.log('[Pin] Initializing pinned banner');
            const bannerToggle = document.getElementById('pinnedBannerToggle');
            const bannerCurrent = document.getElementById('pinnedBannerCurrent');
            console.log('[Pin] bannerToggle:', bannerToggle);
            console.log('[Pin] bannerCurrent:', bannerCurrent);

            if (bannerToggle) {
                bannerToggle.addEventListener('click', (e) => {
                    e.stopPropagation();
                    togglePinnedDropdown();
                });
            }

            // Click on banner text to scroll to latest pinned
            if (bannerCurrent) {
                bannerCurrent.addEventListener('click', (e) => {
                    console.log('[Pin] Banner clicked, target:', e.target);
                    if (!e.target.closest('.pinned-banner-toggle')) {
                        if (pinnedMessages.length > 0) {
                            const latestPinned = pinnedMessages[pinnedMessages.length - 1];
                            console.log('[Pin] Scrolling to latest pinned:', latestPinned.msgId);
                            scrollToMessage(latestPinned.msgId);
                        }
                    }
                });
            }

            // Dropdown only closes when toggle button is clicked manually
            // (removed auto-close on outside click)
        }

        // ==================== END PIN MESSAGE FUNCTIONS ====================

        // ==================== PIN NEWS CARD FUNCTIONS ====================

        // Toggle pin state for a news card
        function togglePinNewsCard(url, title, description) {
            const existingIndex = pinnedNewsCards.findIndex(p => p.url === url);

            if (existingIndex !== -1) {
                // Unpin
                pinnedNewsCards.splice(existingIndex, 1);
                console.log('[PinNews] Unpinned news:', url);
            } else {
                // Pin - enforce max limit
                if (pinnedNewsCards.length >= MAX_PINNED_NEWS) {
                    // Remove oldest pinned news
                    pinnedNewsCards.shift();
                }
                pinnedNewsCards.push({
                    url,
                    title,
                    description: description || '',
                    pinnedAt: Date.now()
                });
                console.log('[PinNews] Pinned news:', url);
            }

            // Update all pin button states for this URL
            updateNewsCardPinState(url);

            // Render the pinned news list
            renderPinnedNewsList();

            // 只在 session 已存在時才存檔（釘選不應建立新 session）
            if (currentLoadedSessionId !== null) {
                saveCurrentSession();
            }
        }

        // Update the visual state of pin buttons for a specific URL
        function updateNewsCardPinState(url) {
            const isPinned = pinnedNewsCards.some(p => p.url === url);
            const cards = document.querySelectorAll(`.news-card[data-url="${CSS.escape(url)}"]`);
            cards.forEach(card => {
                const pinBtn = card.querySelector('.news-card-pin');
                if (pinBtn) {
                    pinBtn.classList.toggle('pinned', isPinned);
                    pinBtn.title = isPinned ? '取消釘選' : '釘選新聞';
                }
            });
        }

        // Render the pinned news list in the right tab panel
        function renderPinnedNewsList() {
            const listEl = document.getElementById('pinnedNewsList');
            if (!listEl) return;

            if (pinnedNewsCards.length === 0) {
                listEl.innerHTML = '<div class="pinned-news-empty">尚未釘選任何新聞</div>';
                return;
            }

            listEl.innerHTML = pinnedNewsCards.map(news => `
                <div class="pinned-news-item" data-url="${escapeHTML(news.url)}">
                    <span class="pinned-news-item-icon">📌</span>
                    <span class="pinned-news-item-title">${escapeHTML(news.title)}</span>
                    <button class="pinned-news-item-unpin" title="取消釘選">✕</button>
                </div>
            `).join('');

            // Add event listeners
            listEl.querySelectorAll('.pinned-news-item').forEach(item => {
                const url = item.dataset.url;
                const news = pinnedNewsCards.find(n => n.url === url);

                // Click to open link
                item.addEventListener('click', (e) => {
                    if (!e.target.classList.contains('pinned-news-item-unpin')) {
                        window.open(url, '_blank');
                    }
                });

                // Unpin button
                const unpinBtn = item.querySelector('.pinned-news-item-unpin');
                if (unpinBtn && news) {
                    unpinBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        togglePinNewsCard(news.url, news.title, news.description);
                    });
                }
            });
        }

        // Event delegation for news card pin buttons
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('news-card-pin')) {
                e.preventDefault();
                e.stopPropagation();
                const card = e.target.closest('.news-card');
                if (card) {
                    const url = card.dataset.url;
                    const title = card.dataset.title;
                    const description = card.dataset.description || '';
                    if (url && title) {
                        togglePinNewsCard(url, title, description);
                    }
                }
            }
        });

        // ==================== END PIN NEWS CARD FUNCTIONS ====================

        // Add clarification message to chat (conversational)
        function addClarificationMessage(clarificationData, originalQuery, eventSource, savedQuery) {
            console.log('[Clarification] Adding multi-dimensional clarification:', clarificationData);

            // Hide loading state
            const loadingState = document.getElementById('loadingState');
            if (loadingState) {
                loadingState.classList.remove('active');
            }

            // Get chat elements (should already be active from performDeepResearch)
            const chatMessagesEl = document.getElementById('chatMessages');
            if (!chatMessagesEl) {
                console.error('[Clarification] Chat messages element not found');
                return;
            }

            // Icon mapping for question types
            const iconMap = {
                'time': '🕒',
                'scope': '🎯',
                'entity': '🌐'
            };

            // Create clarification card
            const messageDiv = document.createElement('div');
            messageDiv.className = 'chat-message assistant clarification';

            // Build clarification card HTML
            let contentHTML = '<div class="chat-message-header">AI 助理</div>';
            contentHTML += '<div class="chat-message-bubble">';
            contentHTML += '<div class="clarification-card">';

            // Header with instruction
            contentHTML += `
                <div class="clarification-header">
                    ${clarificationData.instruction || '為了精準搜尋'}「${escapeHTML(originalQuery)}」，請選擇以下條件
                </div>
            `;

            // Render each question block
            clarificationData.questions.forEach(question => {
                const icon = iconMap[question.clarification_type] || '❓';
                const requiredMark = question.required ? '<span class="required">*</span>' : '';

                contentHTML += `
                    <div class="question-block" data-question-id="${question.question_id}">
                        <div class="question-label">
                            <span class="question-icon">${icon}</span>
                            <span class="question-text">${escapeHTML(question.question)}${requiredMark}</span>
                            <span class="multi-select-hint">(可多選)</span>
                        </div>
                        <div class="options-group">
                `;

                // Add option chips
                question.options.forEach(opt => {
                    const queryModifier = opt.query_modifier || '';
                    const isComprehensive = opt.is_comprehensive || false;
                    // Serialize time_range as JSON string for data attribute
                    const timeRangeJson = opt.time_range ? JSON.stringify(opt.time_range) : '';

                    contentHTML += `
                        <button class="option-chip"
                                data-option-id="${opt.id}"
                                data-label="${escapeHTML(opt.label)}"
                                data-query-modifier="${escapeHTML(queryModifier)}"
                                data-is-comprehensive="${isComprehensive}"
                                data-time-range="${escapeHTML(timeRangeJson)}">
                            ${escapeHTML(opt.label)}
                        </button>
                    `;
                });

                // Add "Other" text input option
                contentHTML += `
                    <div class="custom-input-group" style="margin-top: 8px; display: flex; gap: 6px; align-items: center;">
                        <input type="text" class="custom-option-input"
                               placeholder="或自行輸入..."
                               data-question-id="${question.question_id}"
                               style="flex: 1; padding: 6px 10px; border: 1px solid #ddd; border-radius: 16px; font-size: 0.9em;">
                        <button class="option-chip custom-input-confirm"
                                data-question-id="${question.question_id}"
                                style="padding: 6px 12px; background: #e0e0e0;">
                            確定
                        </button>
                    </div>
                `;

                contentHTML += '</div></div>';
            });

            // Global extra focus section (Bug #4: 自由聚焦選項) - redesigned as inline input + confirm
            contentHTML += `
                <div class="clarification-extra-section" style="margin-top: 16px; padding-top: 12px; border-top: 1px solid #e0e0e0;">
                    <div style="font-size: 0.9em; color: #555; margin-bottom: 6px;">
                        或直接輸入您的研究重點：
                    </div>
                    <div class="custom-input-group" style="display: flex; gap: 6px; align-items: center;">
                        <input type="text" class="clarification-extra-focus"
                               placeholder="例如：特定事件、人物、時間段..."
                               style="flex: 1; padding: 6px 10px; border: 1px solid #ddd; border-radius: 16px; font-size: 0.9em;">
                        <button class="option-chip free-start-confirm"
                                style="padding: 6px 12px; background: #e0e0e0;">
                            開始研究
                        </button>
                    </div>
                </div>
            `;

            // Submit button: full width (skip button removed)
            contentHTML += `
                <div class="clarification-actions" style="margin-top: 12px;">
                    <button class="submit-clarification" disabled style="width: 100%;">
                        ${clarificationData.submit_label || '開始搜尋'}
                    </button>
                </div>
            `;

            contentHTML += '</div></div>'; // Close card and bubble

            messageDiv.innerHTML = contentHTML;
            chatMessagesEl.appendChild(messageDiv);
            chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;

            console.log('[Clarification] Multi-question card rendered');

            // Attach event listeners
            attachClarificationListeners(messageDiv, clarificationData, originalQuery, eventSource);
        }

        // Attach event listeners for multi-question clarification
        function attachClarificationListeners(container, clarificationData, originalQuery, eventSource) {
            const questions = clarificationData.questions;
            const selectedAnswers = {}; // {question_id: [{label, query_modifier, is_comprehensive, time_range}]}

            // Helper to check if all questions answered and enable submit
            function updateSubmitButton() {
                const submitBtn = container.querySelector('.submit-clarification');
                const allAnswered = questions.every(q => selectedAnswers[q.question_id] && selectedAnswers[q.question_id].length > 0);
                submitBtn.disabled = !allAnswered;
                if (allAnswered) {
                    console.log('[Clarification] All questions answered, submit enabled');
                }
            }

            // Option chip click handler (multi-select: toggle each chip)
            container.querySelectorAll('.option-chip:not(.custom-input-confirm)').forEach(chip => {
                chip.addEventListener('click', function() {
                    const questionBlock = this.closest('.question-block');
                    const questionId = questionBlock.dataset.questionId;

                    // Initialize array for this question if needed
                    if (!selectedAnswers[questionId]) {
                        selectedAnswers[questionId] = [];
                    }

                    // Toggle this chip's selection
                    const optionId = this.dataset.optionId;
                    const isCurrentlySelected = this.classList.contains('selected');

                    if (isCurrentlySelected) {
                        // Deselect: remove from array
                        this.classList.remove('selected');
                        selectedAnswers[questionId] = selectedAnswers[questionId].filter(a => a.option_id !== optionId);
                    } else {
                        // Select: add to array
                        this.classList.add('selected');

                        // Parse time_range from data attribute if present
                        let timeRange = null;
                        const timeRangeJson = this.dataset.timeRange;
                        if (timeRangeJson) {
                            try {
                                timeRange = JSON.parse(timeRangeJson);
                            } catch (e) {
                                console.warn('[Clarification] Failed to parse time_range:', e);
                            }
                        }

                        selectedAnswers[questionId].push({
                            option_id: optionId,
                            label: this.dataset.label,
                            query_modifier: this.dataset.queryModifier,
                            is_comprehensive: this.dataset.isComprehensive === 'true',
                            time_range: timeRange
                        });

                        // Mutual exclusion: when comprehensive is clicked, deselect all other options
                        if (this.dataset.isComprehensive === 'true') {
                            questionBlock.querySelectorAll('.option-chip:not(.custom-input-confirm)').forEach(otherChip => {
                                if (otherChip === this) return;
                                otherChip.classList.remove('selected');
                            });
                            // Keep only the comprehensive option selected
                            selectedAnswers[questionId] = [{
                                option_id: optionId,
                                label: this.dataset.label,
                                query_modifier: this.dataset.queryModifier,
                                is_comprehensive: true,
                                time_range: timeRange
                            }];
                        }
                    }

                    // Clear custom input when selecting chips
                    const customInput = questionBlock.querySelector('.custom-option-input');
                    if (customInput) customInput.value = '';
                    // Remove custom confirm highlight
                    const confirmBtn = questionBlock.querySelector('.custom-input-confirm');
                    if (confirmBtn) confirmBtn.classList.remove('selected');

                    console.log('[Clarification] Selected:', questionId, selectedAnswers[questionId]);
                    updateSubmitButton();
                });
            });

            // Custom input confirm button handler
            container.querySelectorAll('.custom-input-confirm').forEach(btn => {
                btn.addEventListener('click', function() {
                    const questionId = this.dataset.questionId;
                    const questionBlock = container.querySelector(`.question-block[data-question-id="${questionId}"]`);
                    const customInput = questionBlock.querySelector('.custom-option-input');
                    const customValue = customInput.value.trim();

                    if (!customValue) {
                        alert('請輸入內容');
                        return;
                    }

                    // Deselect all preset chips (custom input replaces chip selections)
                    questionBlock.querySelectorAll('.option-chip:not(.custom-input-confirm)').forEach(c => c.classList.remove('selected'));

                    // Highlight confirm button as selected
                    this.classList.add('selected');

                    // Store custom input as the only answer for this question
                    selectedAnswers[questionId] = [{
                        option_id: '_custom',
                        label: customValue,
                        query_modifier: customValue,
                        is_comprehensive: false
                    }];

                    console.log('[Clarification] Custom input:', questionId, selectedAnswers[questionId]);
                    updateSubmitButton();
                });
            });

            // Allow Enter key to confirm custom input
            container.querySelectorAll('.custom-option-input').forEach(input => {
                input.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') {
                        const questionId = this.dataset.questionId;
                        const confirmBtn = container.querySelector(`.custom-input-confirm[data-question-id="${questionId}"]`);
                        if (confirmBtn) confirmBtn.click();
                    }
                });
            });

            // Free start button handler (opens research with extra focus text, skipping selections)
            const freeStartBtn = container.querySelector('.free-start-confirm');
            if (freeStartBtn) {
                freeStartBtn.addEventListener('click', () => {
                    const extraInput = container.querySelector('.clarification-extra-focus');
                    const extraFocus = extraInput ? extraInput.value.trim() : '';
                    submitClarification(selectedAnswers, originalQuery, eventSource, questions, extraFocus, true);
                });
            }

            // Submit button handler
            container.querySelector('.submit-clarification').addEventListener('click', () => {
                const extraFocusInput = container.querySelector('.clarification-extra-focus');
                const extraFocus = extraFocusInput ? extraFocusInput.value.trim() : '';
                submitClarification(selectedAnswers, originalQuery, eventSource, questions, extraFocus);
            });
        }

        // Submit clarification response with natural language query building
        function submitClarification(selectedAnswers, originalQuery, eventSource, questions, extraFocus = '', forceAllComprehensive = false) {
            console.log('[Clarification] Submitting answers:', selectedAnswers);
            console.log('[Clarification] Original query:', originalQuery);
            console.log('[Clarification] Extra focus:', extraFocus, 'Force comprehensive:', forceAllComprehensive);

            // Prevent duplicate submissions: find and disable all clarification buttons
            const clarificationCards = document.querySelectorAll('.clarification-card');
            clarificationCards.forEach(card => {
                card.querySelectorAll('button').forEach(btn => {
                    btn.disabled = true;
                    btn.style.opacity = '0.5';
                    btn.style.pointerEvents = 'none';
                });
                card.querySelectorAll('input').forEach(inp => {
                    inp.disabled = true;
                    inp.style.opacity = '0.5';
                });
            });

            // Close event source
            if (eventSource) {
                eventSource.close();
            }

            // Build clarified query using natural language (方案 B)
            let clarifiedQuery = originalQuery;
            let allComprehensive = true;

            // Separate answers by clarification type
            let timeModifier = '';
            let scopeModifier = '';
            let entityModifier = '';
            let userTimeRange = null;  // NEW: structured time range from clarification
            let userTimeLabel = null;  // NEW: user's label for the time selection

            questions.forEach(q => {
                const answers = selectedAnswers[q.question_id];
                if (!answers || answers.length === 0) return;

                // Check if all selected options are comprehensive
                answers.forEach(answer => {
                    if (!answer.is_comprehensive) {
                        allComprehensive = false;
                    }
                });

                // Merge modifiers from multiple selections
                const modifiers = answers.map(a => a.query_modifier).filter(Boolean);
                const mergedModifier = modifiers.join('、');

                // Collect modifiers by type
                if (mergedModifier) {
                    if (q.clarification_type === 'time') {
                        timeModifier = mergedModifier;
                        // Extract structured time_range from last selected time option
                        const lastWithTimeRange = [...answers].reverse().find(a => a.time_range);
                        if (lastWithTimeRange) {
                            userTimeRange = lastWithTimeRange.time_range;
                            userTimeLabel = lastWithTimeRange.label;
                            console.log('[Clarification] User selected time range:', userTimeRange, 'label:', userTimeLabel);
                        }
                    } else if (q.clarification_type === 'scope') {
                        scopeModifier = mergedModifier;
                    } else if (q.clarification_type === 'entity') {
                        entityModifier = mergedModifier;
                    }
                }
            });

            // Build natural language query
            // Strategy: time modifier goes before, scope modifier goes after
            if (timeModifier && scopeModifier) {
                // Example: "蔡英文卸任後的兩岸政策，聚焦外交關係"
                clarifiedQuery = `${originalQuery}(${timeModifier}，${scopeModifier})`;
            } else if (timeModifier) {
                // Example: "蔡英文兩岸政策(任期內)"
                clarifiedQuery = `${originalQuery}(${timeModifier})`;
            } else if (scopeModifier) {
                // Example: "momo科技(營運財報面向)"
                clarifiedQuery = `${originalQuery}(${scopeModifier})`;
            } else if (entityModifier) {
                // Example: "晶片法案(美國)"
                clarifiedQuery = `${entityModifier}${originalQuery}`;
            }

            // Append extra focus text if provided (Bug #4)
            if (extraFocus) {
                clarifiedQuery += `，${extraFocus}`;
            }

            // Override allComprehensive if skip button was used (Bug #4)
            if (forceAllComprehensive) {
                allComprehensive = true;
            }

            console.log('[Clarification] Clarified query:', clarifiedQuery);
            console.log('[Clarification] All comprehensive:', allComprehensive);
            console.log('[Clarification] User time range:', userTimeRange);

            // Add user message showing selection
            const chatMessagesEl = document.getElementById('chatMessages');
            const userMessageDiv = document.createElement('div');
            userMessageDiv.className = 'chat-message user';

            const selections = Object.values(selectedAnswers).flatMap(arr => arr.map(a => a.label));
            if (extraFocus) selections.push(extraFocus);
            if (forceAllComprehensive && selections.length === 0) selections.push('直接開始研究');
            const selectionText = selections.join(' + ');
            userMessageDiv.innerHTML = `
                <div class="chat-message-header">你</div>
                <div class="chat-message-bubble">${escapeHTML(selectionText)}</div>
            `;
            chatMessagesEl.appendChild(userMessageDiv);
            chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;

            // Re-submit with skip_clarification flag AND user-selected time range
            console.log('[Clarification] Re-submitting with skip_clarification=true');
            performDeepResearch(clarifiedQuery, true, allComprehensive, userTimeRange, userTimeLabel);
        }

        // View tabs
        const tabs = document.querySelectorAll('.tab');
        const researchView = document.getElementById('researchView');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const view = tab.dataset.view;

                // Update active tab
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');

                // Switch views (three-way: list / timeline / research)
                if (view === 'list') {
                    listView.style.display = 'flex';
                    timelineView.classList.remove('active');
                    if (researchView) researchView.classList.remove('active');
                    summaryToggle.classList.add('active');
                } else if (view === 'timeline') {
                    listView.style.display = 'none';
                    timelineView.classList.add('active');
                    if (researchView) researchView.classList.remove('active');
                    summaryToggle.classList.add('active');
                } else if (view === 'research') {
                    listView.style.display = 'none';
                    timelineView.classList.remove('active');
                    if (researchView) researchView.classList.add('active');
                    summaryToggle.classList.remove('active'); // Hide summary toggle in research view
                }
            });
        });

        // Summary toggle
        btnToggleSummary.addEventListener('click', () => {
            if (!summaryExpanded) {
                // Expand summary - just show the descriptions that are already loaded
                showSummaries();
                summaryExpanded = true;
                btnToggleSummary.textContent = '📝 收起摘要';
            } else {
                // Collapse summary
                hideSummaries();
                summaryExpanded = false;
                btnToggleSummary.textContent = '📝 展開摘要';
            }
        });

        function showSummaries() {
            // Show excerpts in both list and timeline views
            const listExcerpts = listView.querySelectorAll('.news-excerpt');
            listExcerpts.forEach(excerpt => excerpt.classList.add('visible'));

            const timelineExcerpts = timelineView.querySelectorAll('.news-excerpt');
            timelineExcerpts.forEach(excerpt => excerpt.classList.add('visible'));
        }

        function hideSummaries() {
            // Hide excerpts in both list and timeline views
            const listExcerpts = listView.querySelectorAll('.news-excerpt');
            listExcerpts.forEach(excerpt => excerpt.classList.remove('visible'));

            const timelineExcerpts = timelineView.querySelectorAll('.news-excerpt');
            timelineExcerpts.forEach(excerpt => excerpt.classList.remove('visible'));
        }

        // Share modal
        btnShare.addEventListener('click', () => {
            modalOverlay.classList.add('active');
        });

        btnCloseModal.addEventListener('click', () => {
            modalOverlay.classList.remove('active');
            shareContentOverride = null; // Clear override when closing
        });

        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay) {
                modalOverlay.classList.remove('active');
                shareContentOverride = null; // Clear override when closing
            }
        });

        // Track delete confirmation state
        let deleteConfirmTimeout = null;

        // Function to handle delete session with two-click confirmation
        function handleDeleteSession(sessionId, deleteBtn) {
            if (deleteBtn.classList.contains('confirming')) {
                // Second click - actually delete
                deleteSavedSession(sessionId);
            } else {
                // First click - show confirmation
                deleteBtn.classList.add('confirming');
                deleteBtn.textContent = '確定刪除';

                // Clear any existing timeout
                if (deleteConfirmTimeout) {
                    clearTimeout(deleteConfirmTimeout);
                }

                // Reset after 3 seconds if not confirmed
                deleteConfirmTimeout = setTimeout(() => {
                    deleteBtn.classList.remove('confirming');
                    deleteBtn.textContent = '✕';
                }, 3000);
            }
        }

        // Function to delete a saved session
        function deleteSavedSession(sessionId) {
            console.log('Deleting session:', sessionId);
            cancelActiveSearch();

            // Remove from savedSessions array
            savedSessions = savedSessions.filter(s => s.id !== sessionId);

            // Update localStorage
            localStorage.setItem('taiwanNewsSavedSessions', JSON.stringify(savedSessions));

            // If the deleted session is currently loaded, reset the interface
            if (currentLoadedSessionId === sessionId) {
                currentLoadedSessionId = null;
                conversationHistory = [];
                sessionHistory = [];
                chatHistory = [];
                accumulatedArticles = [];
                pinnedMessages = [];
                pinnedNewsCards = [];
                currentResearchReport = null;
                currentConversationId = null;

                resetToHome();
                searchInput.value = '';
                initialState.style.display = 'block';

                renderConversationHistory();
            }

            document.dispatchEvent(new CustomEvent('session-deleted'));
        }

        // Function to load a saved session
        function loadSavedSession(session) {
            console.log('Loading saved session:', session);
            cancelActiveSearch();

            // Track this session's ID to prevent duplicate saves
            currentLoadedSessionId = session.id;

            // Restore conversation history and session data
            conversationHistory = [...session.conversationHistory];
            sessionHistory = [...session.sessionHistory];

            // Restore chat history and accumulated articles (if they exist)
            chatHistory = session.chatHistory ? [...session.chatHistory] : [];
            accumulatedArticles = session.accumulatedArticles ? [...session.accumulatedArticles] : [];
            pinnedMessages = session.pinnedMessages ? [...session.pinnedMessages] : [];
            pinnedNewsCards = session.pinnedNewsCards ? [...session.pinnedNewsCards] : [];

            // Restore Deep Research report for follow-up Q&A
            currentResearchReport = session.researchReport ? { ...session.researchReport } : null;
            if (currentResearchReport) {
                console.log('[Session] Restored research report:', currentResearchReport.report?.substring(0, 100) + '...');

                // Restore reasoning chain data for sharing
                currentArgumentGraph = session.researchReport?.argumentGraph ? [...session.researchReport.argumentGraph] : null;
                currentChainAnalysis = session.researchReport?.chainAnalysis ? { ...session.researchReport.chainAnalysis } : null;
                if (currentArgumentGraph) {
                    console.log('[Session] Restored argument graph with', currentArgumentGraph.length, 'nodes');
                }
            } else {
                // Clear reasoning chain data if no report
                currentArgumentGraph = null;
                currentChainAnalysis = null;
            }

            // 先重置 UI 到首頁狀態
            resetToHome();
            const aiSummarySec = document.getElementById('aiSummarySection');
            if (aiSummarySec) aiSummarySec.style.display = 'none';

            // Render the last query's results
            if (sessionHistory.length > 0) {
                const lastSession = sessionHistory[sessionHistory.length - 1];
                populateResultsFromAPI(lastSession.data, lastSession.query);

                // resetToHome() 移除了 .active class，恢復 session 後需要重新加上
                resultsSection.classList.add('active');
                initialState.style.display = 'none';
            }

            // Update conversation history display
            renderConversationHistory();

            // Restore chat UI if there were chat messages
            if (chatHistory.length > 0) {
                console.log(`Restoring ${chatHistory.length} chat messages`);
                chatMessagesEl.innerHTML = ''; // Clear existing messages

                // Re-render all chat messages with pin buttons
                chatHistory.forEach(msg => {
                    const messageDiv = document.createElement('div');
                    messageDiv.className = `chat-message ${msg.role}`;

                    // Use existing msgId or generate one for legacy messages
                    const msgId = msg.msgId || `msg-${msg.timestamp}-${Math.random().toString(36).substr(2, 9)}`;
                    messageDiv.setAttribute('data-msg-id', msgId);

                    const headerText = msg.role === 'user' ? '你' : 'AI 助理';

                    // Format content based on role
                    // Use marked.js for assistant messages, escape HTML for user messages
                    let formattedContent = msg.content;
                    if (msg.role === 'assistant') {
                        formattedContent = marked.parse(msg.content);
                    } else {
                        formattedContent = escapeHTML(msg.content);
                    }

                    // Check if this message is pinned
                    const isPinned = pinnedMessages.some(p => p.msgId === msgId);

                    messageDiv.innerHTML = `
                        <div class="chat-message-header">${headerText}</div>
                        <div class="chat-message-content-wrapper">
                            <div class="chat-message-bubble">${formattedContent}</div>
                            <button class="chat-message-pin ${isPinned ? 'pinned' : ''}" data-msg-id="${msgId}" title="${isPinned ? '取消釘選' : '釘選訊息'}">📌</button>
                        </div>
                    `;

                    // Add click handler for pin button
                    const pinBtn = messageDiv.querySelector('.chat-message-pin');
                    pinBtn.addEventListener('click', () => togglePinMessage(msgId, msg.content, msg.role));

                    chatMessagesEl.appendChild(messageDiv);
                });

                // Show chat container if we restored messages
                chatContainer.classList.add('active');

                // Render pinned banner
                renderPinnedBanner();

                // Optionally switch to chat mode
                currentMode = 'chat';
                modeButtons.forEach(btn => btn.classList.remove('active')); modeButtons[2].classList.add('active');
                modeButtonsInline.forEach(btn => btn.classList.remove('active'));
                const chatInlineBtn = document.querySelector('.mode-btn-inline[data-mode="chat"]');
                if (chatInlineBtn) chatInlineBtn.classList.add('active');
                btnSearch.textContent = '發送';
                searchInput.placeholder = '研究助理會參考摘要內容及您釘選的文章來回答...';

                // Move search container into chat area
                chatInputContainer.appendChild(searchContainer);
                chatInputContainer.style.display = 'block';

                // Scroll to bottom of chat
                chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
            }

            // Render pinned news list (outside of chat block since news cards are separate)
            renderPinnedNewsList();

            // Restore Deep Research report in research view if available
            if (currentResearchReport && currentResearchReport.report) {
                const researchViewEl = document.getElementById('researchView');
                if (researchViewEl) {
                    console.log('[Session] Restoring research report to research view');
                    researchViewEl.innerHTML = '';

                    // Create report container
                    const reportContainer = document.createElement('div');
                    reportContainer.className = 'deep-research-report';
                    reportContainer.style.cssText = 'padding: 20px; max-width: 900px; margin: 0 auto;';

                    // Convert markdown to HTML
                    let reportHTML = marked.parse(currentResearchReport.report);

                    // Add citation links if sources are available
                    if (currentResearchReport.sources && currentResearchReport.sources.length > 0) {
                        reportHTML = addCitationLinks(reportHTML, currentResearchReport.sources);
                    }

                    // Apply collapsible sections
                    reportHTML = addCollapsibleSections(reportHTML);

                    // Append citation reference list (toggle)
                    if (currentResearchReport.sources && currentResearchReport.sources.length > 0) {
                        reportHTML += generateCitationReferenceList(currentResearchReport.sources);
                    }

                    reportContainer.innerHTML = reportHTML;
                    researchViewEl.appendChild(reportContainer);

                    // Bind collapsible handlers
                    bindCollapsibleHandlers(researchViewEl);

                    // Add toggle-all toolbar
                    addToggleAllToolbar(reportContainer);

                    // Restore reasoning chain if available
                    if (currentArgumentGraph && currentArgumentGraph.length > 0) {
                        displayReasoningChainInContainer(currentArgumentGraph, currentChainAnalysis, researchViewEl);
                        console.log('[Session] Restored reasoning chain in research view');
                    }

                    // Show results section and switch to research tab
                    resultsSection.classList.add('active');
                    const researchTab = document.querySelector('.tab[data-view="research"]');
                    if (researchTab) {
                        researchTab.click();
                    }
                }
            } else {
                // No research report in this session — clear any leftover report display
                const researchViewEl = document.getElementById('researchView');
                if (researchViewEl) {
                    researchViewEl.innerHTML = '';
                }
            }

            // Hide initial state (session has content)
            initialState.style.display = 'none';
            resultsSection.style.display = '';  // Clear inline style so CSS class takes effect
            // resultsSection.active is already set in the sessionHistory block above (if needed)
            // 確保資料夾頁面關閉（不走 hideFolderPage 以免覆蓋我們剛設好的狀態）
            const _fp = document.getElementById('folderPage');
            if (_fp) _fp.style.display = 'none';
            _preFolderState = null;
            // 確保搜尋容器可見
            searchContainer.style.display = 'block';

            // Refresh sidebar to sync active session highlight
            renderLeftSidebarSessions();
        }

        // ===== Export/Share Functions =====

        // Helper: Clean HTML content for different export formats
        function cleanHTMLContent(content, format = 'plain') {
            if (!content) return '';

            if (format === 'plain') {
                // Strip all HTML and markdown links
                return content
                    .replace(/<br\s*\/?>/gi, '\n')
                    .replace(/<[^>]+>/g, '')
                    .replace(/\[來源\]\([^\)]+\)/g, '')
                    .replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1'); // Keep link text only
            } else if (format === 'markdown') {
                // Keep markdown, convert <br> to newlines
                return content.replace(/<br\s*\/?>/gi, '\n\n');
            }

            return content;
        }

        // Helper: Get top 10 articles from the most recent search
        function getTop10Articles() {
            if (sessionHistory.length === 0) return [];
            const lastSession = sessionHistory[sessionHistory.length - 1];
            if (!lastSession.data || !lastSession.data.content) return [];
            return lastSession.data.content.slice(0, 10);
        }

        // Format content for plain text export
        function formatPlainText() {
            let content = '';
            const date = new Date().toLocaleDateString('zh-TW', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });

            content += `台灣新聞搜尋結果\n`;
            content += `日期：${date}\n`;
            content += `${'='.repeat(50)}\n\n`;

            // Search queries
            if (conversationHistory.length > 0) {
                content += `【搜尋查詢】\n`;
                conversationHistory.forEach((query, idx) => {
                    content += `${idx + 1}. ${query}\n`;
                });
                content += `\n`;
            }

            // AI answers from search results
            if (sessionHistory.length > 0) {
                content += `【AI 分析摘要】\n`;
                sessionHistory.forEach((session, idx) => {
                    if (session.data && session.data.answer) {
                        const plainAnswer = cleanHTMLContent(session.data.answer, 'plain');
                        content += `${plainAnswer}\n\n`;
                    }
                });
            }

            // Free conversation messages
            if (chatHistory.length > 0) {
                content += `【自由對話紀錄】\n`;
                chatHistory.forEach(msg => {
                    const icon = msg.role === 'user' ? '👤 你' : '🤖 AI';
                    const plainContent = cleanHTMLContent(msg.content, 'plain');
                    content += `${icon}：${plainContent}\n\n`;
                });
            }

            // Top 10 articles
            const top10 = getTop10Articles();
            if (top10.length > 0) {
                content += `【相關新聞文章（${top10.length} 篇）】\n`;
                top10.forEach((article, idx) => {
                    const title = article.name || article.schema_object?.headline || '無標題';
                    const source = article.schema_object?.publisher?.name || article.site || '未知來源';
                    const date = article.schema_object?.datePublished?.split('T')[0] || '未知日期';
                    const desc = article.description || article.ranking?.description || '';

                    content += `${idx + 1}. ${title}\n`;
                    content += `   來源：${source} | 日期：${date}\n`;
                    if (desc) {
                        content += `   ${desc}\n`;
                    }
                    content += `\n`;
                });
            }

            return content;
        }

        // Format content for AI chatbot (ChatGPT/Claude/Gemini)
        function formatForAIChatbot() {
            let content = '';

            // Opening context
            if (conversationHistory.length > 0) {
                content += `我剛搜尋了關於「${conversationHistory[0]}」的台灣新聞，以下是搜尋結果：\n\n`;
            }

            // Search queries
            if (conversationHistory.length > 1) {
                content += `【搜尋查詢】\n`;
                conversationHistory.forEach((query, idx) => {
                    content += `${idx + 1}. ${query}\n`;
                });
                content += `\n`;
            }

            // AI analysis
            if (sessionHistory.length > 0) {
                content += `【AI 分析摘要】\n`;
                sessionHistory.forEach((session, idx) => {
                    if (session.data && session.data.answer) {
                        const cleanAnswer = cleanHTMLContent(session.data.answer, 'markdown');
                        content += `${cleanAnswer}\n\n`;
                    }
                });
            }

            // Free conversation
            if (chatHistory.length > 0) {
                content += `【自由對話紀錄】\n`;
                chatHistory.forEach(msg => {
                    const icon = msg.role === 'user' ? '👤 你' : '🤖 AI';
                    const cleanContent = cleanHTMLContent(msg.content, 'markdown');
                    content += `${icon}：${cleanContent}\n\n`;
                });
            }

            // Articles with URLs
            const top10 = getTop10Articles();
            if (top10.length > 0) {
                content += `【相關新聞來源（${top10.length} 篇）】\n`;
                top10.forEach((article, idx) => {
                    const title = article.name || article.schema_object?.headline || '無標題';
                    const url = article.url || article.schema_object?.url || '';
                    const source = article.schema_object?.publisher?.name || article.site || '';
                    const date = article.schema_object?.datePublished?.split('T')[0] || '';
                    const desc = article.description || article.ranking?.description || '';

                    content += `${idx + 1}. ${title}\n`;
                    if (url) content += `   網址：${url}\n`;
                    if (source || date) content += `   來源：${source} | 日期：${date}\n`;
                    if (desc) content += `   摘要：${desc}\n`;
                    content += `\n`;
                });
            }

            content += `---\n請基於以上資訊幫我進行分析。`;

            return content;
        }

        // Format content for NotebookLM (rich markdown with full details)
        function formatForNotebookLM() {
            let content = '';
            const date = new Date().toLocaleDateString('zh-TW', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });

            // Title
            if (conversationHistory.length > 0) {
                content += `# 台灣新聞搜尋：${conversationHistory[0]}\n\n`;
            } else {
                content += `# 台灣新聞搜尋結果\n\n`;
            }

            content += `**搜尋日期**: ${date}\n\n`;
            content += `---\n\n`;

            // Search queries
            if (conversationHistory.length > 0) {
                content += `## 搜尋查詢\n\n`;
                conversationHistory.forEach((query, idx) => {
                    content += `${idx + 1}. ${query}\n`;
                });
                content += `\n`;
            }

            // AI analysis
            if (sessionHistory.length > 0) {
                content += `## AI 分析摘要\n\n`;
                sessionHistory.forEach((session, idx) => {
                    if (session.data && session.data.answer) {
                        const cleanAnswer = cleanHTMLContent(session.data.answer, 'markdown');
                        content += `${cleanAnswer}\n\n`;
                    }
                });
            }

            // Free conversation
            if (chatHistory.length > 0) {
                content += `## 自由對話紀錄\n\n`;
                chatHistory.forEach(msg => {
                    const role = msg.role === 'user' ? '**你**' : '**AI 助理**';
                    const cleanContent = cleanHTMLContent(msg.content, 'markdown');
                    content += `${role}: ${cleanContent}\n\n`;
                });
            }

            // Detailed articles
            const top10 = getTop10Articles();
            if (top10.length > 0) {
                content += `## 相關新聞來源（${top10.length} 篇）\n\n`;
                top10.forEach((article, idx) => {
                    const title = article.name || article.schema_object?.headline || '無標題';
                    const url = article.url || article.schema_object?.url || '';
                    const source = article.schema_object?.publisher?.name || article.site || '';
                    const date = article.schema_object?.datePublished?.split('T')[0] || '';
                    const desc = article.description || article.ranking?.description || '';

                    content += `### ${idx + 1}. ${title}\n\n`;
                    if (source) content += `- **來源**: ${source}\n`;
                    if (date) content += `- **日期**: ${date}\n`;
                    if (url) content += `- **網址**: ${url}\n`;
                    if (desc) content += `\n${desc}\n`;
                    content += `\n---\n\n`;
                });
            }

            return content;
        }

        // Copy to clipboard and optionally open URL
        async function copyAndOpen(text, url = null, buttonElement) {
            const originalText = buttonElement.textContent;

            try {
                await navigator.clipboard.writeText(text);

                // Visual feedback
                buttonElement.textContent = '✓ 已複製！';
                buttonElement.style.borderColor = '#059669';
                buttonElement.style.color = '#059669';

                // Open URL if provided
                if (url) {
                    window.open(url, '_blank');
                }

                setTimeout(() => {
                    buttonElement.textContent = originalText;
                    buttonElement.style.borderColor = '';
                    buttonElement.style.color = '';
                }, 2000);

            } catch (err) {
                console.error('複製失敗:', err);
                buttonElement.textContent = '✗ 複製失敗';
                setTimeout(() => {
                    buttonElement.textContent = originalText;
                }, 2000);
            }
        }

        // Button handlers
        const btnCopyPlainText = document.getElementById('btnCopyPlainText');
        const btnCopyChatGPT = document.getElementById('btnCopyChatGPT');
        const btnCopyClaude = document.getElementById('btnCopyClaude');
        const btnCopyGemini = document.getElementById('btnCopyGemini');
        const btnCopyNotebookLM = document.getElementById('btnCopyNotebookLM');

        btnCopyPlainText.addEventListener('click', () => {
            const content = shareContentOverride || formatPlainText();
            copyAndOpen(content, null, btnCopyPlainText);
        });

        btnCopyChatGPT.addEventListener('click', () => {
            const content = shareContentOverride || formatForAIChatbot();
            copyAndOpen(content, 'https://chat.openai.com/', btnCopyChatGPT);
        });

        btnCopyClaude.addEventListener('click', () => {
            const content = shareContentOverride || formatForAIChatbot();
            copyAndOpen(content, 'https://claude.ai/', btnCopyClaude);
        });

        btnCopyGemini.addEventListener('click', () => {
            const content = shareContentOverride || formatForAIChatbot();
            copyAndOpen(content, 'https://gemini.google.com/', btnCopyGemini);
        });

        btnCopyNotebookLM.addEventListener('click', () => {
            const content = shareContentOverride || formatForNotebookLM();
            copyAndOpen(content, 'https://notebooklm.google.com/', btnCopyNotebookLM);
        });

        // Feedback buttons — open modal for user comment (Bug #14)
        const feedbackButtons = document.querySelectorAll('.btn-feedback');
        feedbackButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const rating = btn.dataset.rating || (btn.textContent.includes('👍') ? 'positive' : 'negative');
                openFeedbackModal(rating);
            });
        });

        // Feedback modal logic (Bug #14)
        function openFeedbackModal(rating) {
            // Remove existing modal if any
            const existing = document.getElementById('feedbackModal');
            if (existing) existing.remove();

            const ratingLabel = rating === 'positive' ? '👍 正面回饋' : '👎 負面回饋';

            const modal = document.createElement('div');
            modal.id = 'feedbackModal';
            modal.className = 'feedback-modal-overlay';
            modal.innerHTML = `
                <div class="feedback-modal">
                    <div class="feedback-modal-header">
                        <span>${ratingLabel}</span>
                        <button class="feedback-modal-close">&times;</button>
                    </div>
                    <div class="feedback-modal-body">
                        <textarea class="feedback-textarea"
                                  placeholder="感謝提供意見，有任何正面、負面體驗，或其他意見都歡迎回饋！"
                                  rows="4"></textarea>
                    </div>
                    <div class="feedback-modal-footer">
                        <button class="feedback-cancel">取消</button>
                        <button class="feedback-submit">提交回饋</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);

            // Focus textarea
            const textarea = modal.querySelector('.feedback-textarea');
            setTimeout(() => textarea.focus(), 100);

            // Close handlers
            modal.querySelector('.feedback-modal-close').addEventListener('click', () => modal.remove());
            modal.querySelector('.feedback-cancel').addEventListener('click', () => modal.remove());
            modal.addEventListener('click', (e) => {
                if (e.target === modal) modal.remove();
            });

            // Submit handler
            modal.querySelector('.feedback-submit').addEventListener('click', async () => {
                const comment = textarea.value.trim();
                const submitBtn = modal.querySelector('.feedback-submit');
                submitBtn.disabled = true;
                submitBtn.textContent = '提交中...';

                // Gather context
                const query = document.getElementById('searchInput')?.value || '';
                const summaryEl = document.querySelector('.summary-content');
                const answerSnippet = summaryEl ? summaryEl.textContent.substring(0, 200) : '';

                try {
                    const resp = await fetch('/api/feedback', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            rating: rating,
                            query: query,
                            answer_snippet: answerSnippet,
                            comment: comment,
                            session_id: currentSessionId || ''
                        })
                    });
                    if (resp.ok) {
                        submitBtn.textContent = '已提交';
                        submitBtn.style.background = '#059669';
                        submitBtn.style.color = '#fff';
                        setTimeout(() => modal.remove(), 1000);
                    } else {
                        submitBtn.textContent = '提交失敗，請重試';
                        submitBtn.disabled = false;
                    }
                } catch (err) {
                    console.error('[Feedback] Submit error:', err);
                    submitBtn.textContent = '提交失敗，請重試';
                    submitBtn.disabled = false;
                }
            });
        }

        // ==================== SOURCE TREE VIEW (VS Code Style) ====================

        // Source folders data structure
        // { id: string, name: string, isUncategorized: boolean, siteNames: string[] }
        let sourceFolders = [];
        const SOURCE_FOLDERS_KEY = 'nlweb_source_folders';
        const UNCATEGORIZED_FOLDER_ID = '__uncategorized__';

        // Load source folders from localStorage
        function loadSourceFolders() {
            try {
                const stored = localStorage.getItem(SOURCE_FOLDERS_KEY);
                if (stored) {
                    sourceFolders = JSON.parse(stored);
                    // Ensure uncategorized folder exists
                    if (!sourceFolders.find(f => f.id === UNCATEGORIZED_FOLDER_ID)) {
                        sourceFolders.unshift({
                            id: UNCATEGORIZED_FOLDER_ID,
                            name: '未分類',
                            isUncategorized: true,
                            siteNames: [],
                            collapsed: false
                        });
                    }
                } else {
                    // Initialize with just uncategorized
                    sourceFolders = [{
                        id: UNCATEGORIZED_FOLDER_ID,
                        name: '未分類',
                        isUncategorized: true,
                        siteNames: [],
                        collapsed: false
                    }];
                }
            } catch (e) {
                console.error('Failed to load source folders:', e);
                sourceFolders = [{
                    id: UNCATEGORIZED_FOLDER_ID,
                    name: '未分類',
                    isUncategorized: true,
                    siteNames: [],
                    collapsed: false
                }];
            }
        }

        // Save source folders to localStorage
        function saveSourceFolders() {
            try {
                localStorage.setItem(SOURCE_FOLDERS_KEY, JSON.stringify(sourceFolders));
            } catch (e) {
                console.error('Failed to save source folders:', e);
            }
        }

        // Load available sites from backend
        async function loadSiteFilters() {
            loadSourceFolders();
            try {
                const response = await fetch('/sites_config');
                const data = await response.json();

                if (data.sites && Array.isArray(data.sites)) {
                    availableSites = data.sites;
                    // By default, all sites are selected
                    selectedSites = availableSites.map(s => s.name);

                    // Distribute sites to folders
                    distributeToFolders();
                    renderSourceTreeView();
                }
            } catch (error) {
                console.error('Failed to load site filters:', error);
                const container = document.getElementById('sourceTreeView');
                if (container) {
                    container.innerHTML = '<div class="tree-view-empty" style="color: #dc2626;">載入失敗</div>';
                }
            }
        }

        // Distribute sites to folders, putting uncategorized ones in the uncategorized folder
        function distributeToFolders() {
            const categorizedSites = new Set();
            sourceFolders.forEach(folder => {
                if (!folder.isUncategorized) {
                    folder.siteNames.forEach(name => categorizedSites.add(name));
                }
            });

            // Put remaining sites in uncategorized
            const uncategorizedFolder = sourceFolders.find(f => f.id === UNCATEGORIZED_FOLDER_ID);
            if (uncategorizedFolder) {
                uncategorizedFolder.siteNames = availableSites
                    .map(s => s.name)
                    .filter(name => !categorizedSites.has(name));
            }
        }

        // Render source tree view
        function renderSourceTreeView() {
            const container = document.getElementById('sourceTreeView');
            if (!container) return;

            if (availableSites.length === 0) {
                container.innerHTML = '<div class="tree-view-empty">沒有可用的來源</div>';
                return;
            }

            let html = '';

            // Render each folder
            sourceFolders.forEach(folder => {
                const sites = folder.siteNames
                    .map(name => availableSites.find(s => s.name === name))
                    .filter(Boolean);

                const isCollapsed = folder.collapsed ? 'collapsed' : '';
                const folderIconClass = folder.collapsed ? 'closed' : 'open';

                html += `
                <div class="tree-folder ${isCollapsed}" data-folder-id="${folder.id}">
                    <div class="tree-folder-header" data-folder-id="${folder.id}">
                        <span class="tree-folder-chevron">
                            <svg viewBox="0 0 16 16" fill="currentColor">
                                <path fill-rule="evenodd" d="M4.646 1.646a.5.5 0 0 1 .708 0l6 6a.5.5 0 0 1 0 .708l-6 6a.5.5 0 0 1-.708-.708L10.293 8 4.646 2.354a.5.5 0 0 1 0-.708z"/>
                            </svg>
                        </span>
                        <span class="tree-folder-icon ${folderIconClass}">
                            <svg viewBox="0 0 16 16" fill="currentColor">
                                <path d="M.54 3.87.5 3a2 2 0 0 1 2-2h3.672a2 2 0 0 1 1.414.586l.828.828A2 2 0 0 0 9.828 3H13.5a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-11a2 2 0 0 1-2-2V3.87z"/>
                            </svg>
                        </span>
                        <span class="tree-folder-name ${folder.isUncategorized ? 'uncategorized' : ''}">${escapeHTML(folder.name)}</span>
                        <span class="tree-folder-count">(${sites.length})</span>
                        ${!folder.isUncategorized ? `
                        <div class="tree-folder-actions">
                            <div class="tree-folder-menu">
                                <button class="tree-folder-menu-btn" title="更多選項">⋯</button>
                                <div class="tree-folder-dropdown">
                                    <button class="tree-folder-dropdown-item" data-action="rename" data-folder-id="${folder.id}">重新命名</button>
                                    <button class="tree-folder-dropdown-item danger" data-action="delete" data-folder-id="${folder.id}">刪除資料夾</button>
                                </div>
                            </div>
                        </div>
                        ` : ''}
                    </div>
                    <div class="tree-folder-content">
                        ${sites.map(site => {
                            const fullText = site.description || site.name;
                            const dashIndex = fullText.indexOf(' - ');
                            const mainName = dashIndex > -1 ? fullText.substring(0, dashIndex) : fullText;
                            const subInfo = dashIndex > -1 ? fullText.substring(dashIndex + 3) : '';
                            return `
                        <div class="tree-item tree-item-two-line" draggable="true" data-site-name="${site.name}" data-folder-id="${folder.id}">
                            <input type="checkbox" class="tree-item-checkbox"
                                   ${selectedSites.includes(site.name) ? 'checked' : ''}
                                   data-site-name="${site.name}">
                            <div class="tree-item-text">
                                <span class="tree-item-main" title="${fullText}">${mainName}</span>
                                ${subInfo ? `<span class="tree-item-sub">${subInfo}</span>` : ''}
                            </div>
                        </div>
                            `;
                        }).join('')}
                    </div>
                </div>
                `;
            });

            container.innerHTML = html;
            bindSourceTreeEvents(container);
        }

        // Bind events for source tree view
        function bindSourceTreeEvents(container) {
            // Folder toggle (collapse/expand)
            container.querySelectorAll('.tree-folder-header').forEach(header => {
                header.addEventListener('click', (e) => {
                    // Don't toggle if clicking on actions or checkbox
                    if (e.target.closest('.tree-folder-actions') || e.target.closest('.tree-folder-menu')) return;

                    const folderId = header.dataset.folderId;
                    const folder = sourceFolders.find(f => f.id === folderId);
                    if (folder) {
                        folder.collapsed = !folder.collapsed;
                        saveSourceFolders();
                        renderSourceTreeView();
                    }
                });

                // Drag over folder header
                header.addEventListener('dragover', (e) => {
                    e.preventDefault();
                    header.classList.add('drag-over');
                });

                header.addEventListener('dragleave', () => {
                    header.classList.remove('drag-over');
                });

                header.addEventListener('drop', (e) => {
                    e.preventDefault();
                    header.classList.remove('drag-over');
                    const siteName = e.dataTransfer.getData('text/site-name');
                    const targetFolderId = header.dataset.folderId;
                    if (siteName && targetFolderId) {
                        moveSiteToFolder(siteName, targetFolderId);
                    }
                });
            });

            // Checkbox toggle
            container.querySelectorAll('.tree-item-checkbox').forEach(checkbox => {
                checkbox.addEventListener('change', (e) => {
                    e.stopPropagation();
                    const siteName = checkbox.dataset.siteName;
                    toggleSiteFilter(siteName);
                });

                checkbox.addEventListener('click', (e) => {
                    e.stopPropagation();
                });
            });

            // Item drag
            container.querySelectorAll('.tree-item[draggable="true"]').forEach(item => {
                item.addEventListener('dragstart', (e) => {
                    e.dataTransfer.setData('text/site-name', item.dataset.siteName);
                    e.dataTransfer.effectAllowed = 'move';
                    item.classList.add('dragging');

                    // Create custom drag preview
                    const preview = document.createElement('div');
                    preview.className = 'tree-drag-preview';
                    preview.textContent = item.dataset.siteName;
                    document.body.appendChild(preview);
                    e.dataTransfer.setDragImage(preview, 0, 0);
                    setTimeout(() => preview.remove(), 0);
                });

                item.addEventListener('dragend', () => {
                    item.classList.remove('dragging');
                });
            });

            // Folder menu dropdown
            container.querySelectorAll('.tree-folder-menu-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const dropdown = btn.nextElementSibling;

                    // Close other dropdowns
                    container.querySelectorAll('.tree-folder-dropdown.visible').forEach(d => {
                        if (d !== dropdown) d.classList.remove('visible');
                    });

                    dropdown.classList.toggle('visible');
                });
            });

            // Folder dropdown actions
            container.querySelectorAll('.tree-folder-dropdown-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const action = item.dataset.action;
                    const folderId = item.dataset.folderId;

                    // Close dropdown
                    item.closest('.tree-folder-dropdown').classList.remove('visible');

                    if (action === 'rename') {
                        startRenamingFolder(folderId);
                    } else if (action === 'delete') {
                        deleteSourceFolder(folderId);
                    }
                });
            });

            // Close dropdowns when clicking outside
            document.addEventListener('click', () => {
                container.querySelectorAll('.tree-folder-dropdown.visible').forEach(d => {
                    d.classList.remove('visible');
                });
            });
        }

        // Move a site to a different folder
        function moveSiteToFolder(siteName, targetFolderId) {
            // Remove from current folder
            sourceFolders.forEach(folder => {
                const index = folder.siteNames.indexOf(siteName);
                if (index > -1) {
                    folder.siteNames.splice(index, 1);
                }
            });

            // Add to target folder
            const targetFolder = sourceFolders.find(f => f.id === targetFolderId);
            if (targetFolder && !targetFolder.siteNames.includes(siteName)) {
                targetFolder.siteNames.push(siteName);
            }

            saveSourceFolders();
            renderSourceTreeView();
            console.log(`[Tree] Moved "${siteName}" to folder "${targetFolder?.name}"`);
        }

        // Add new source folder
        function addSourceFolder() {
            const container = document.getElementById('sourceTreeView');
            if (!container) return;

            // Check if already adding
            if (container.querySelector('.tree-new-folder-row')) return;

            const row = document.createElement('div');
            row.className = 'tree-new-folder-row';
            row.innerHTML = `
                <input type="text" class="tree-new-folder-input" placeholder="資料夾名稱" autofocus>
                <button class="tree-new-folder-btn confirm">確定</button>
                <button class="tree-new-folder-btn cancel">取消</button>
            `;

            container.insertBefore(row, container.firstChild);

            const input = row.querySelector('.tree-new-folder-input');
            input.focus();

            const confirmAdd = () => {
                const name = input.value.trim();
                if (name) {
                    const newFolder = {
                        id: 'folder_' + Date.now(),
                        name: name,
                        isUncategorized: false,
                        siteNames: [],
                        collapsed: false
                    };
                    // Insert before uncategorized
                    const uncatIndex = sourceFolders.findIndex(f => f.id === UNCATEGORIZED_FOLDER_ID);
                    if (uncatIndex > -1) {
                        sourceFolders.splice(uncatIndex, 0, newFolder);
                    } else {
                        sourceFolders.push(newFolder);
                    }
                    saveSourceFolders();
                    console.log(`[Tree] Created new folder: "${name}"`);
                }
                row.remove();
                renderSourceTreeView();
            };

            row.querySelector('.tree-new-folder-btn.confirm').addEventListener('click', confirmAdd);
            row.querySelector('.tree-new-folder-btn.cancel').addEventListener('click', () => row.remove());
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') confirmAdd();
                if (e.key === 'Escape') row.remove();
            });
        }

        // Start renaming a folder
        function startRenamingFolder(folderId) {
            const folder = sourceFolders.find(f => f.id === folderId);
            if (!folder || folder.isUncategorized) return;

            const header = document.querySelector(`.tree-folder-header[data-folder-id="${folderId}"]`);
            if (!header) return;

            const nameEl = header.querySelector('.tree-folder-name');
            const originalName = folder.name;

            const input = document.createElement('input');
            input.type = 'text';
            input.className = 'tree-folder-rename-input';
            input.value = originalName;

            nameEl.replaceWith(input);
            input.focus();
            input.select();

            const finishRename = () => {
                const newName = input.value.trim();
                if (newName && newName !== originalName) {
                    folder.name = newName;
                    saveSourceFolders();
                    console.log(`[Tree] Renamed folder to: "${newName}"`);
                }
                renderSourceTreeView();
            };

            input.addEventListener('blur', finishRename);
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    finishRename();
                }
                if (e.key === 'Escape') {
                    e.preventDefault();
                    renderSourceTreeView();
                }
            });
        }

        // Delete a source folder (move contents to uncategorized)
        function deleteSourceFolder(folderId) {
            const folder = sourceFolders.find(f => f.id === folderId);
            if (!folder || folder.isUncategorized) return;

            // Move all sites to uncategorized
            const uncategorized = sourceFolders.find(f => f.id === UNCATEGORIZED_FOLDER_ID);
            if (uncategorized) {
                folder.siteNames.forEach(siteName => {
                    if (!uncategorized.siteNames.includes(siteName)) {
                        uncategorized.siteNames.push(siteName);
                    }
                });
            }

            // Remove folder
            sourceFolders = sourceFolders.filter(f => f.id !== folderId);
            saveSourceFolders();
            renderSourceTreeView();
            console.log(`[Tree] Deleted folder: "${folder.name}", moved ${folder.siteNames.length} sites to uncategorized`);
        }

        // Toggle individual site filter
        function toggleSiteFilter(siteName) {
            const index = selectedSites.indexOf(siteName);
            if (index > -1) {
                selectedSites.splice(index, 1);
            } else {
                selectedSites.push(siteName);
            }
        }

        // Toggle all sites
        function toggleAllSites() {
            const allSelected = selectedSites.length === availableSites.length;
            if (allSelected) {
                selectedSites = [];
            } else {
                selectedSites = availableSites.map(s => s.name);
            }
            renderSourceTreeView();
        }

        // Expand all source folders
        function expandAllSourceFolders() {
            sourceFolders.forEach(f => f.collapsed = false);
            saveSourceFolders();
            renderSourceTreeView();
        }

        // Collapse all source folders
        function collapseAllSourceFolders() {
            sourceFolders.forEach(f => f.collapsed = true);
            saveSourceFolders();
            renderSourceTreeView();
        }

        // Legacy function for compatibility
        function renderSiteFilters() {
            renderSourceTreeView();
        }

        // Get selected sites as parameter value
        function getSelectedSitesParam() {
            // If all sites are selected or none selected, return 'all'
            if (selectedSites.length === 0 || selectedSites.length === availableSites.length) {
                return 'all';
            }
            return selectedSites.join(',');
        }

        // Toggle private sources checkbox
        function togglePrivateSources() {
            const checkbox = document.getElementById('includePrivateSourcesCheckbox');
            includePrivateSources = checkbox.checked;
            console.log('Include private sources:', includePrivateSources);

            // 勾選時自動開啟右側「我的檔案」面板
            if (includePrivateSources) {
                openTab('files');
            }
        }

        // Bind toolbar buttons for source tree
        document.getElementById('btnAddSourceFolder')?.addEventListener('click', addSourceFolder);
        document.getElementById('btnExpandAllSources')?.addEventListener('click', expandAllSourceFolders);
        document.getElementById('btnCollapseAllSources')?.addEventListener('click', collapseAllSourceFolders);
        document.getElementById('btnToggleAllSites')?.addEventListener('click', toggleAllSites);

        // Trigger file input click
        function triggerFileUpload() {
            document.getElementById('fileInput').click();
        }

        // Handle file selection
        async function handleFileSelect(event) {
            const file = event.target.files[0];
            if (!file) return;

            console.log('File selected:', file.name, file.size, 'bytes');

            // Show upload modal
            const modal = document.getElementById('uploadModal');
            const progressBar = document.getElementById('progressBarFill');
            const progressText = document.getElementById('progressText');

            modal.classList.add('visible');
            progressBar.style.width = '0%';
            progressText.textContent = '準備上傳...';

            try {
                // Create form data
                const formData = new FormData();
                formData.append('file', file);
                formData.append('user_id', TEMP_USER_ID);

                // Upload file
                progressText.textContent = '正在上傳文件...';
                const response = await fetch('/api/user/upload', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || '上傳失敗');
                }

                const result = await response.json();
                console.log('Upload result:', result);

                const sourceId = result.source_id;

                // Connect to SSE for progress updates
                progressText.textContent = '正在處理文件...';
                const eventSource = new EventSource(`/api/user/upload/${sourceId}/progress?user_id=${TEMP_USER_ID}`);

                eventSource.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    console.log('Progress:', data);

                    progressBar.style.width = data.progress + '%';
                    progressText.textContent = data.message;

                    if (data.status === 'completed') {
                        eventSource.close();
                        setTimeout(() => {
                            modal.classList.remove('visible');
                            loadUserFiles(); // Refresh file list
                        }, 1000);
                    } else if (data.status === 'failed') {
                        eventSource.close();
                        alert('文件處理失敗: ' + data.message);
                        modal.classList.remove('visible');
                    }
                };

                eventSource.onerror = (error) => {
                    console.error('SSE error:', error);
                    eventSource.close();
                    modal.classList.remove('visible');
                    alert('處理過程中斷，請稍後再試');
                };

            } catch (error) {
                console.error('Upload error:', error);
                alert('上傳失敗: ' + error.message);
                modal.classList.remove('visible');
            }

            // Reset file input
            event.target.value = '';
        }

        // ==================== FILE TREE VIEW (VS Code Style) ====================

        // File folders data structure
        // { id: string, name: string, isUncategorized: boolean, fileIds: string[] }
        let fileFolders = [];
        const FILE_FOLDERS_KEY = 'nlweb_file_folders';
        const UNCATEGORIZED_FILE_FOLDER_ID = '__uncategorized_files__';

        // Selected files for context (checked files)
        let selectedFileIds = new Set();
        const SELECTED_FILES_KEY = 'nlweb_selected_files';

        // Load file folders from localStorage
        function loadFileFolders() {
            try {
                const stored = localStorage.getItem(FILE_FOLDERS_KEY);
                if (stored) {
                    fileFolders = JSON.parse(stored);
                    if (!fileFolders.find(f => f.id === UNCATEGORIZED_FILE_FOLDER_ID)) {
                        fileFolders.unshift({
                            id: UNCATEGORIZED_FILE_FOLDER_ID,
                            name: '未分類',
                            isUncategorized: true,
                            fileIds: [],
                            collapsed: false
                        });
                    }
                } else {
                    fileFolders = [{
                        id: UNCATEGORIZED_FILE_FOLDER_ID,
                        name: '未分類',
                        isUncategorized: true,
                        fileIds: [],
                        collapsed: false
                    }];
                }

                // Load selected files
                const selectedStored = localStorage.getItem(SELECTED_FILES_KEY);
                if (selectedStored) {
                    selectedFileIds = new Set(JSON.parse(selectedStored));
                }
            } catch (e) {
                console.error('Failed to load file folders:', e);
                fileFolders = [{
                    id: UNCATEGORIZED_FILE_FOLDER_ID,
                    name: '未分類',
                    isUncategorized: true,
                    fileIds: [],
                    collapsed: false
                }];
            }
        }

        // Save file folders to localStorage
        function saveFileFolders() {
            try {
                localStorage.setItem(FILE_FOLDERS_KEY, JSON.stringify(fileFolders));
            } catch (e) {
                console.error('Failed to save file folders:', e);
            }
        }

        // Save selected files to localStorage
        function saveSelectedFiles() {
            try {
                localStorage.setItem(SELECTED_FILES_KEY, JSON.stringify([...selectedFileIds]));
            } catch (e) {
                console.error('Failed to save selected files:', e);
            }
        }

        // Load user files list
        async function loadUserFiles() {
            loadFileFolders();
            try {
                const response = await fetch(`/api/user/sources?user_id=${TEMP_USER_ID}`);
                if (!response.ok) {
                    throw new Error('Failed to load files');
                }

                const result = await response.json();
                userFiles = result.sources || [];
                console.log('Loaded user files:', userFiles);

                // Distribute files to folders
                distributeFilesToFolders();
                renderFileTreeView();
            } catch (error) {
                console.error('Error loading files:', error);
            }
        }

        // Distribute files to folders
        function distributeFilesToFolders() {
            const categorizedFileIds = new Set();
            fileFolders.forEach(folder => {
                if (!folder.isUncategorized) {
                    folder.fileIds.forEach(id => categorizedFileIds.add(id));
                }
            });

            // Put remaining files in uncategorized
            const uncategorizedFolder = fileFolders.find(f => f.id === UNCATEGORIZED_FILE_FOLDER_ID);
            if (uncategorizedFolder) {
                uncategorizedFolder.fileIds = userFiles
                    .map(f => f.source_id)
                    .filter(id => !categorizedFileIds.has(id));
            }

            // Clean up selected files that no longer exist
            const existingIds = new Set(userFiles.map(f => f.source_id));
            selectedFileIds = new Set([...selectedFileIds].filter(id => existingIds.has(id)));
            saveSelectedFiles();
        }

        // Render file tree view
        function renderFileTreeView() {
            const container = document.getElementById('fileTreeView');
            if (!container) return;

            // Show empty state only if no folders (except uncategorized) AND no files
            const hasCustomFolders = fileFolders.some(f => !f.isUncategorized);
            if (userFiles.length === 0 && !hasCustomFolders) {
                container.innerHTML = '<div class="tree-view-empty">尚未上傳文件</div>';
                return;
            }

            let html = '';

            // Render each folder
            fileFolders.forEach(folder => {
                const files = folder.fileIds
                    .map(id => userFiles.find(f => f.source_id === id))
                    .filter(Boolean);

                const isCollapsed = folder.collapsed ? 'collapsed' : '';
                const folderIconClass = folder.collapsed ? 'closed' : 'open';

                html += `
                <div class="tree-folder ${isCollapsed}" data-folder-id="${folder.id}">
                    <div class="tree-folder-header" data-folder-id="${folder.id}">
                        <span class="tree-folder-chevron">
                            <svg viewBox="0 0 16 16" fill="currentColor">
                                <path fill-rule="evenodd" d="M4.646 1.646a.5.5 0 0 1 .708 0l6 6a.5.5 0 0 1 0 .708l-6 6a.5.5 0 0 1-.708-.708L10.293 8 4.646 2.354a.5.5 0 0 1 0-.708z"/>
                            </svg>
                        </span>
                        <span class="tree-folder-icon ${folderIconClass}">
                            <svg viewBox="0 0 16 16" fill="currentColor">
                                <path d="M.54 3.87.5 3a2 2 0 0 1 2-2h3.672a2 2 0 0 1 1.414.586l.828.828A2 2 0 0 0 9.828 3H13.5a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-11a2 2 0 0 1-2-2V3.87z"/>
                            </svg>
                        </span>
                        <span class="tree-folder-name ${folder.isUncategorized ? 'uncategorized' : ''}">${escapeHTML(folder.name)}</span>
                        <span class="tree-folder-count">(${files.length})</span>
                        ${!folder.isUncategorized ? `
                        <div class="tree-folder-actions">
                            <div class="tree-folder-menu">
                                <button class="tree-folder-menu-btn" title="更多選項">⋯</button>
                                <div class="tree-folder-dropdown">
                                    <button class="tree-folder-dropdown-item" data-action="rename" data-folder-id="${folder.id}">重新命名</button>
                                    <button class="tree-folder-dropdown-item danger" data-action="delete" data-folder-id="${folder.id}">刪除資料夾</button>
                                </div>
                            </div>
                        </div>
                        ` : ''}
                    </div>
                    <div class="tree-folder-content">
                        ${files.map(file => {
                            const icon = getFileIcon(file.file_type);
                            const statusText = getStatusText(file.status);
                            const isSelected = selectedFileIds.has(file.source_id);
                            const canDelete = file.status !== 'processing';

                            return `
                            <div class="tree-item" draggable="true" data-file-id="${file.source_id}" data-folder-id="${folder.id}">
                                <input type="checkbox" class="tree-item-checkbox"
                                       ${isSelected ? 'checked' : ''}
                                       ${file.status !== 'ready' ? 'disabled' : ''}
                                       data-file-id="${file.source_id}"
                                       title="${file.status === 'ready' ? '勾選以包含在搜尋中' : '處理中，無法選取'}">
                                <span class="tree-item-icon">${icon}</span>
                                <span class="tree-item-name" title="${file.name}">${file.name}</span>
                                <span class="tree-item-status ${file.status}">${statusText}</span>
                                ${canDelete ? `
                                <div class="tree-item-actions">
                                    <button class="tree-item-action-btn delete" data-file-id="${file.source_id}" data-file-name="${file.name}" title="刪除檔案">🗑️</button>
                                </div>
                                ` : ''}
                            </div>
                            `;
                        }).join('')}
                    </div>
                </div>
                `;
            });

            container.innerHTML = html;
            bindFileTreeEvents(container);
        }

        // Bind events for file tree view
        function bindFileTreeEvents(container) {
            // Folder toggle
            container.querySelectorAll('.tree-folder-header').forEach(header => {
                header.addEventListener('click', (e) => {
                    if (e.target.closest('.tree-folder-actions') || e.target.closest('.tree-folder-menu')) return;

                    const folderId = header.dataset.folderId;
                    const folder = fileFolders.find(f => f.id === folderId);
                    if (folder) {
                        folder.collapsed = !folder.collapsed;
                        saveFileFolders();
                        renderFileTreeView();
                    }
                });

                // Drag over folder header
                header.addEventListener('dragover', (e) => {
                    e.preventDefault();
                    header.classList.add('drag-over');
                });

                header.addEventListener('dragleave', () => {
                    header.classList.remove('drag-over');
                });

                header.addEventListener('drop', (e) => {
                    e.preventDefault();
                    header.classList.remove('drag-over');
                    const fileId = e.dataTransfer.getData('text/file-id');
                    const targetFolderId = header.dataset.folderId;
                    if (fileId && targetFolderId) {
                        moveFileToFolder(fileId, targetFolderId);
                    }
                });
            });

            // Checkbox toggle (select file for context)
            container.querySelectorAll('.tree-item-checkbox').forEach(checkbox => {
                checkbox.addEventListener('change', (e) => {
                    e.stopPropagation();
                    const fileId = checkbox.dataset.fileId;
                    if (checkbox.checked) {
                        selectedFileIds.add(fileId);
                    } else {
                        selectedFileIds.delete(fileId);
                    }
                    saveSelectedFiles();
                    updateIncludePrivateSourcesState();
                    console.log('[FileTree] Selected files:', [...selectedFileIds]);
                });

                checkbox.addEventListener('click', (e) => {
                    e.stopPropagation();
                });
            });

            // Item drag
            container.querySelectorAll('.tree-item[draggable="true"]').forEach(item => {
                item.addEventListener('dragstart', (e) => {
                    e.dataTransfer.setData('text/file-id', item.dataset.fileId);
                    e.dataTransfer.effectAllowed = 'move';
                    item.classList.add('dragging');

                    const preview = document.createElement('div');
                    preview.className = 'tree-drag-preview';
                    const file = userFiles.find(f => f.source_id === item.dataset.fileId);
                    preview.textContent = file?.name || item.dataset.fileId;
                    document.body.appendChild(preview);
                    e.dataTransfer.setDragImage(preview, 0, 0);
                    setTimeout(() => preview.remove(), 0);
                });

                item.addEventListener('dragend', () => {
                    item.classList.remove('dragging');
                });
            });

            // Delete button
            container.querySelectorAll('.tree-item-action-btn.delete').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const fileId = btn.dataset.fileId;
                    const fileName = btn.dataset.fileName;
                    deleteUserFile(fileId, fileName);
                });
            });

            // Folder menu dropdown
            container.querySelectorAll('.tree-folder-menu-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const dropdown = btn.nextElementSibling;
                    container.querySelectorAll('.tree-folder-dropdown.visible').forEach(d => {
                        if (d !== dropdown) d.classList.remove('visible');
                    });
                    dropdown.classList.toggle('visible');
                });
            });

            // Folder dropdown actions
            container.querySelectorAll('.tree-folder-dropdown-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const action = item.dataset.action;
                    const folderId = item.dataset.folderId;
                    item.closest('.tree-folder-dropdown').classList.remove('visible');

                    if (action === 'rename') {
                        startRenamingFileFolder(folderId);
                    } else if (action === 'delete') {
                        deleteFileFolder(folderId);
                    }
                });
            });

            // Close dropdowns
            document.addEventListener('click', () => {
                container.querySelectorAll('.tree-folder-dropdown.visible').forEach(d => {
                    d.classList.remove('visible');
                });
            });
        }

        // Update the includePrivateSources state based on selected files
        function updateIncludePrivateSourcesState() {
            includePrivateSources = selectedFileIds.size > 0;
        }

        // Get selected file IDs for search context
        function getSelectedFileIds() {
            return [...selectedFileIds];
        }

        // Move a file to a different folder
        function moveFileToFolder(fileId, targetFolderId) {
            fileFolders.forEach(folder => {
                const index = folder.fileIds.indexOf(fileId);
                if (index > -1) {
                    folder.fileIds.splice(index, 1);
                }
            });

            const targetFolder = fileFolders.find(f => f.id === targetFolderId);
            if (targetFolder && !targetFolder.fileIds.includes(fileId)) {
                targetFolder.fileIds.push(fileId);
            }

            saveFileFolders();
            renderFileTreeView();
            const file = userFiles.find(f => f.source_id === fileId);
            console.log(`[FileTree] Moved "${file?.name}" to folder "${targetFolder?.name}"`);
        }

        // Add new file folder
        function addFileFolder() {
            const container = document.getElementById('fileTreeView');
            if (!container) return;
            if (container.querySelector('.tree-new-folder-row')) return;

            const row = document.createElement('div');
            row.className = 'tree-new-folder-row';
            row.innerHTML = `
                <input type="text" class="tree-new-folder-input" placeholder="資料夾名稱" autofocus>
                <button class="tree-new-folder-btn confirm">確定</button>
                <button class="tree-new-folder-btn cancel">取消</button>
            `;

            container.insertBefore(row, container.firstChild);

            const input = row.querySelector('.tree-new-folder-input');
            input.focus();

            const confirmAdd = () => {
                const name = input.value.trim();
                if (name) {
                    const newFolder = {
                        id: 'file_folder_' + Date.now(),
                        name: name,
                        isUncategorized: false,
                        fileIds: [],
                        collapsed: false
                    };
                    const uncatIndex = fileFolders.findIndex(f => f.id === UNCATEGORIZED_FILE_FOLDER_ID);
                    if (uncatIndex > -1) {
                        fileFolders.splice(uncatIndex, 0, newFolder);
                    } else {
                        fileFolders.push(newFolder);
                    }
                    saveFileFolders();
                    console.log(`[FileTree] Created new folder: "${name}"`);
                }
                row.remove();
                renderFileTreeView();
            };

            row.querySelector('.tree-new-folder-btn.confirm').addEventListener('click', confirmAdd);
            row.querySelector('.tree-new-folder-btn.cancel').addEventListener('click', () => row.remove());
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') confirmAdd();
                if (e.key === 'Escape') row.remove();
            });
        }

        // Start renaming a file folder
        function startRenamingFileFolder(folderId) {
            const folder = fileFolders.find(f => f.id === folderId);
            if (!folder || folder.isUncategorized) return;

            const header = document.querySelector(`#fileTreeView .tree-folder-header[data-folder-id="${folderId}"]`);
            if (!header) return;

            const nameEl = header.querySelector('.tree-folder-name');
            const originalName = folder.name;

            const input = document.createElement('input');
            input.type = 'text';
            input.className = 'tree-folder-rename-input';
            input.value = originalName;

            nameEl.replaceWith(input);
            input.focus();
            input.select();

            const finishRename = () => {
                const newName = input.value.trim();
                if (newName && newName !== originalName) {
                    folder.name = newName;
                    saveFileFolders();
                    console.log(`[FileTree] Renamed folder to: "${newName}"`);
                }
                renderFileTreeView();
            };

            input.addEventListener('blur', finishRename);
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    finishRename();
                }
                if (e.key === 'Escape') {
                    e.preventDefault();
                    renderFileTreeView();
                }
            });
        }

        // Delete a file folder
        function deleteFileFolder(folderId) {
            const folder = fileFolders.find(f => f.id === folderId);
            if (!folder || folder.isUncategorized) return;

            const uncategorized = fileFolders.find(f => f.id === UNCATEGORIZED_FILE_FOLDER_ID);
            if (uncategorized) {
                folder.fileIds.forEach(fileId => {
                    if (!uncategorized.fileIds.includes(fileId)) {
                        uncategorized.fileIds.push(fileId);
                    }
                });
            }

            fileFolders = fileFolders.filter(f => f.id !== folderId);
            saveFileFolders();
            renderFileTreeView();
            console.log(`[FileTree] Deleted folder: "${folder.name}"`);
        }

        // Expand all file folders
        function expandAllFileFolders() {
            fileFolders.forEach(f => f.collapsed = false);
            saveFileFolders();
            renderFileTreeView();
        }

        // Collapse all file folders
        function collapseAllFileFolders() {
            fileFolders.forEach(f => f.collapsed = true);
            saveFileFolders();
            renderFileTreeView();
        }

        // Legacy function for compatibility
        function renderFileList() {
            renderFileTreeView();
        }

        // Delete a user file
        async function deleteUserFile(sourceId, fileName) {
            if (!confirm(`確定要刪除「${fileName}」嗎？此操作無法復原。`)) {
                return;
            }

            try {
                const response = await fetch(`/api/user/sources/${sourceId}?user_id=${TEMP_USER_ID}`, {
                    method: 'DELETE'
                });

                if (!response.ok) {
                    const result = await response.json();
                    throw new Error(result.error || 'Failed to delete file');
                }

                // Remove from selected files
                selectedFileIds.delete(sourceId);
                saveSelectedFiles();

                console.log(`File deleted: ${fileName} (source_id=${sourceId})`);
                loadUserFiles();
            } catch (error) {
                console.error('Error deleting file:', error);
                alert('刪除失敗: ' + error.message);
            }
        }

        // Get file icon based on type
        function getFileIcon(fileType) {
            const icons = {
                '.pdf': '📄',
                '.docx': '📝',
                '.txt': '📃',
                '.md': '📋'
            };
            return icons[fileType] || '📄';
        }

        // Get status text
        function getStatusText(status) {
            const texts = {
                'uploading': '上傳中',
                'processing': '處理中',
                'ready': '就緒',
                'failed': '失敗'
            };
            return texts[status] || status;
        }

        // Bind toolbar buttons for file tree
        document.getElementById('btnAddFileFolder')?.addEventListener('click', addFileFolder);
        document.getElementById('btnExpandAllFiles')?.addEventListener('click', expandAllFileFolders);
        document.getElementById('btnCollapseAllFiles')?.addEventListener('click', collapseAllFileFolders);

        // ==================== LEFT SIDEBAR SESSION LIST ====================

        function renderLeftSidebarSessions() {
            const container = document.getElementById('leftSidebarSessions');
            if (!container) return;

            if (savedSessions.length === 0) {
                container.innerHTML = '';
                return;
            }

            // 最新的在最上面，最多顯示 15 條
            const recent = savedSessions.slice().reverse().slice(0, 15);
            container.innerHTML = recent.map(session => {
                const isActive = currentLoadedSessionId === session.id;
                return `<div class="left-sidebar-session-item${isActive ? ' active' : ''}" data-sidebar-session-id="${session.id}">
                    <span class="left-sidebar-session-title">${escapeHTML(session.title)}</span>
                    <button class="left-sidebar-session-menu-btn" data-menu-session-id="${session.id}">&#8943;</button>
                    <div class="left-sidebar-session-dropdown" data-dropdown-session-id="${session.id}">
                        <button class="left-sidebar-session-dropdown-item" data-action="rename" data-session-id="${session.id}">重新命名</button>
                        <button class="left-sidebar-session-dropdown-item danger" data-action="delete" data-session-id="${session.id}">刪除</button>
                    </div>
                </div>`;
            }).join('');

            // Click on session item to load (ignore menu/dropdown clicks)
            container.querySelectorAll('.left-sidebar-session-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    if (e.target.closest('.left-sidebar-session-menu-btn') || e.target.closest('.left-sidebar-session-dropdown')) return;
                    const sessionId = parseInt(item.dataset.sidebarSessionId);
                    const session = savedSessions.find(s => s.id === sessionId);
                    if (session) {
                        // 切換前先保存當前對話（防止深度報告等狀態丟失）
                        if (sessionHistory.length > 0 || currentResearchReport) {
                            saveCurrentSession();
                        }
                        loadSavedSession(session);
                    }
                });
            });

            // "..." menu button toggle
            container.querySelectorAll('.left-sidebar-session-menu-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const sid = btn.dataset.menuSessionId;
                    const dropdown = container.querySelector(`.left-sidebar-session-dropdown[data-dropdown-session-id="${sid}"]`);
                    // Close all other dropdowns first
                    container.querySelectorAll('.left-sidebar-session-dropdown.visible').forEach(d => {
                        if (d !== dropdown) d.classList.remove('visible');
                    });
                    dropdown.classList.toggle('visible');
                });
            });

            // Dropdown actions (rename / delete)
            container.querySelectorAll('.left-sidebar-session-dropdown-item').forEach(actionBtn => {
                actionBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const action = actionBtn.dataset.action;
                    const sessionId = parseInt(actionBtn.dataset.sessionId);
                    if (action === 'delete') {
                        deleteSavedSession(sessionId);
                    } else if (action === 'rename') {
                        startSidebarSessionRename(sessionId);
                    }
                });
            });

            // 若處於資料夾管理模式，重新綁定拖曳
            if (_folderModeActive) {
                makeSidebarSessionsDraggable();
            }
        }

        // Close sidebar session dropdowns on outside click
        document.addEventListener('click', () => {
            const container = document.getElementById('leftSidebarSessions');
            if (container) {
                container.querySelectorAll('.left-sidebar-session-dropdown.visible').forEach(d => {
                    d.classList.remove('visible');
                });
            }
        });

        // Inline rename for sidebar sessions
        function startSidebarSessionRename(sessionId) {
            const container = document.getElementById('leftSidebarSessions');
            if (!container) return;
            const item = container.querySelector(`.left-sidebar-session-item[data-sidebar-session-id="${sessionId}"]`);
            if (!item) return;

            const session = savedSessions.find(s => s.id === sessionId);
            if (!session) return;

            // Close dropdown
            const dropdown = item.querySelector('.left-sidebar-session-dropdown');
            if (dropdown) dropdown.classList.remove('visible');

            // Replace title span with input
            const titleSpan = item.querySelector('.left-sidebar-session-title');
            const menuBtn = item.querySelector('.left-sidebar-session-menu-btn');
            if (menuBtn) menuBtn.style.display = 'none';

            const input = document.createElement('input');
            input.type = 'text';
            input.className = 'left-sidebar-session-rename';
            input.value = session.title;
            titleSpan.replaceWith(input);
            input.focus();
            input.select();

            function commitRename() {
                const newName = input.value.trim();
                if (newName && newName !== session.title) {
                    session.title = newName;
                    session.updatedAt = Date.now();
                    localStorage.setItem('taiwanNewsSavedSessions', JSON.stringify(savedSessions));
                }
                renderLeftSidebarSessions();
            }

            input.addEventListener('blur', commitRename);
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') { input.blur(); }
                if (e.key === 'Escape') {
                    input.removeEventListener('blur', commitRename);
                    renderLeftSidebarSessions();
                }
            });
        }

        // 資料夾相關旗標（須在任何引用它們的函式呼叫前宣告，避免 let TDZ）
        let _folderModeActive = false;
        let _preFolderState = null;

        // 監聽 session 變更事件，同步更新左側邊欄
        document.addEventListener('session-saved', renderLeftSidebarSessions);
        document.addEventListener('session-deleted', renderLeftSidebarSessions);

        // Initial render
        renderLeftSidebarSessions();

        // ==================== FOLDER/PROJECT SYSTEM ====================

        // Folder data model - persisted in localStorage
        let folders = [];
        try {
            const storedFolders = localStorage.getItem('taiwanNewsFolders');
            if (storedFolders) {
                folders = JSON.parse(storedFolders);
                console.log(`[Folder] Loaded ${folders.length} folders from localStorage`);
            }
        } catch (e) {
            console.error('[Folder] Failed to load folders from localStorage:', e);
        }

        let currentFolderSort = 'all';
        let currentFolderFilter = '';
        let currentOpenFolderId = null; // Which folder detail is open
        let openDropdownFolderId = null; // Which folder's context menu is open

        function saveFolders() {
            localStorage.setItem('taiwanNewsFolders', JSON.stringify(folders));
        }

        function createFolder(name) {
            const folder = {
                id: Date.now(),
                name: name || '未命名資料夾',
                sessionIds: [],
                createdAt: Date.now(),
                updatedAt: Date.now()
            };
            folders.push(folder);
            saveFolders();
            renderFolderGrid();
            return folder;
        }

        function renameFolder(folderId, newName) {
            const folder = folders.find(f => f.id === folderId);
            if (!folder) return;
            folder.name = newName;
            folder.updatedAt = Date.now();
            saveFolders();
            renderFolderGrid();
        }

        function deleteFolder(folderId) {
            folders = folders.filter(f => f.id !== folderId);
            saveFolders();
            if (currentOpenFolderId === folderId) {
                currentOpenFolderId = null;
                showFolderMain();
            }
            renderFolderGrid();
        }

        function addSessionToFolder(folderId, sessionId) {
            const folder = folders.find(f => f.id === folderId);
            if (!folder) return;
            if (folder.sessionIds.includes(sessionId)) return; // already in folder
            folder.sessionIds.push(sessionId);
            folder.updatedAt = Date.now();
            saveFolders();
        }

        function removeSessionFromFolder(folderId, sessionId) {
            const folder = folders.find(f => f.id === folderId);
            if (!folder) return;
            folder.sessionIds = folder.sessionIds.filter(id => id !== sessionId);
            folder.updatedAt = Date.now();
            saveFolders();
        }

        // -- View switching: show folder page, hide other main content --

        function showFolderPage() {
            const ids = ['initialState', 'searchContainer', 'resultsSection', 'loadingState'];
            // 快照目前每個元素的 display 值（含 chat 相關元素）
            _preFolderState = {};
            ids.forEach(id => {
                const el = document.getElementById(id);
                _preFolderState[id] = el ? el.style.display : '';
            });
            _preFolderState._chatContainerActive = chatContainer.classList.contains('active');
            _preFolderState._chatInputDisplay = chatInputContainer.style.display;

            // 隱藏主要內容，顯示資料夾頁
            ids.forEach(id => {
                const el = document.getElementById(id);
                if (el) el.style.display = 'none';
            });
            chatContainer.classList.remove('active');
            chatInputContainer.style.display = 'none';
            document.getElementById('folderPage').style.display = 'block';

            showFolderMain();
            renderFolderGrid();

            // 進入資料夾管理模式：啟用 sidebar session 拖曳
            _folderModeActive = true;
            makeSidebarSessionsDraggable();
        }

        function hideFolderPage() {
            // 離開資料夾管理模式：關閉 sidebar session 拖曳
            _folderModeActive = false;
            removeSidebarSessionsDraggable();

            document.getElementById('folderPage').style.display = 'none';
            currentOpenFolderId = null;

            // 還原進入前的 UI 狀態
            if (_preFolderState) {
                Object.keys(_preFolderState).forEach(id => {
                    if (id.startsWith('_')) return; // skip special keys
                    const el = document.getElementById(id);
                    if (el) el.style.display = _preFolderState[id];
                });
                // 還原 chat 相關元素
                if (_preFolderState._chatContainerActive) {
                    chatContainer.classList.add('active');
                }
                chatInputContainer.style.display = _preFolderState._chatInputDisplay || '';
                _preFolderState = null;
            } else {
                // fallback：顯示首頁
                document.getElementById('initialState').style.display = 'block';
                document.getElementById('searchContainer').style.display = 'block';
            }
        }

        function showFolderMain() {
            document.getElementById('folderMain').style.display = 'block';
            document.getElementById('folderDetail').style.display = 'none';
            currentOpenFolderId = null;
        }

        function showFolderDetail(folderId) {
            const folder = folders.find(f => f.id === folderId);
            if (!folder) return;

            currentOpenFolderId = folderId;
            document.getElementById('folderMain').style.display = 'none';
            document.getElementById('folderDetail').style.display = 'block';
            document.getElementById('folderDetailTitle').textContent = folder.name;

            renderFolderDetailSessions(folder);
        }

        // -- Rendering --

        function getTimeAgo(timestamp) {
            const diff = Date.now() - timestamp;
            const minutes = Math.floor(diff / 60000);
            if (minutes < 1) return '剛剛';
            if (minutes < 60) return `${minutes} 分鐘前`;
            const hours = Math.floor(minutes / 60);
            if (hours < 24) return `${hours} 小時前`;
            const days = Math.floor(hours / 24);
            return `${days} 天前`;
        }

        function getSortedFolders() {
            let list = [...folders];

            // Apply search filter
            if (currentFolderFilter) {
                list = list.filter(f => f.name.toLowerCase().includes(currentFolderFilter.toLowerCase()));
            }

            // Apply sort
            if (currentFolderSort === 'created') {
                list.sort((a, b) => b.createdAt - a.createdAt);
            } else if (currentFolderSort === 'updated') {
                list.sort((a, b) => b.updatedAt - a.updatedAt);
            }
            // 'all' = original order (newest last, which is push order)

            return list;
        }

        function renderFolderGrid() {
            const grid = document.getElementById('folderGrid');
            if (!grid) return;

            const sortedFolders = getSortedFolders();

            if (sortedFolders.length === 0) {
                grid.innerHTML = '<div class="folder-empty">尚未建立資料夾</div>';
                return;
            }

            grid.innerHTML = sortedFolders.map(folder => `
                <div class="folder-card" data-folder-id="${folder.id}">
                    <div class="folder-card-menu">
                        <button class="folder-card-menu-btn" data-menu-folder-id="${folder.id}">&#8942;</button>
                        <div class="folder-card-dropdown" id="folderDropdown_${folder.id}">
                            <button class="folder-card-dropdown-item" data-action="rename" data-folder-id="${folder.id}">重新命名</button>
                            <button class="folder-card-dropdown-item danger" data-action="delete" data-folder-id="${folder.id}">刪除</button>
                        </div>
                    </div>
                    <div class="folder-card-name" data-name-folder-id="${folder.id}">${escapeHTML(folder.name)}</div>
                    <div class="folder-card-meta">更新時間 ${getTimeAgo(folder.updatedAt)}</div>
                </div>
            `).join('');

            // Bind events
            grid.querySelectorAll('.folder-card').forEach(card => {
                const folderId = parseInt(card.dataset.folderId);

                // Click card → open detail (but not if clicking menu)
                card.addEventListener('click', (e) => {
                    if (e.target.closest('.folder-card-menu')) return;
                    showFolderDetail(folderId);
                });

                // Drag-and-drop: folders accept session drops
                card.addEventListener('dragover', (e) => {
                    e.preventDefault();
                    card.classList.add('drag-over');
                });
                card.addEventListener('dragleave', () => {
                    card.classList.remove('drag-over');
                });
                card.addEventListener('drop', (e) => {
                    e.preventDefault();
                    card.classList.remove('drag-over');
                    const sessionId = parseInt(e.dataTransfer.getData('text/session-id'));
                    if (sessionId) {
                        addSessionToFolder(folderId, sessionId);
                        // 成功閃爍回饋
                        card.classList.add('drop-success');
                        setTimeout(() => card.classList.remove('drop-success'), 600);
                        console.log(`[Folder] Session ${sessionId} added to folder ${folderId}`);
                    }
                });
            });

            // Context menu buttons
            grid.querySelectorAll('.folder-card-menu-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const folderId = parseInt(btn.dataset.menuFolderId);
                    toggleFolderDropdown(folderId);
                });
            });

            // Dropdown actions
            grid.querySelectorAll('.folder-card-dropdown-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const folderId = parseInt(item.dataset.folderId);
                    const action = item.dataset.action;

                    closeFolderDropdowns();

                    if (action === 'rename') {
                        startFolderRename(folderId);
                    } else if (action === 'delete') {
                        deleteFolder(folderId);
                    }
                });
            });
        }

        function toggleFolderDropdown(folderId) {
            const dropdown = document.getElementById(`folderDropdown_${folderId}`);
            if (!dropdown) return;

            const isVisible = dropdown.classList.contains('visible');
            closeFolderDropdowns();
            if (!isVisible) {
                dropdown.classList.add('visible');
                openDropdownFolderId = folderId;
            }
        }

        function closeFolderDropdowns() {
            document.querySelectorAll('.folder-card-dropdown.visible').forEach(d => {
                d.classList.remove('visible');
            });
            openDropdownFolderId = null;
        }

        // Close dropdowns when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.folder-card-menu')) {
                closeFolderDropdowns();
            }
        });

        function startFolderRename(folderId) {
            const nameEl = document.querySelector(`[data-name-folder-id="${folderId}"]`);
            if (!nameEl) return;

            const folder = folders.find(f => f.id === folderId);
            if (!folder) return;

            const input = document.createElement('input');
            input.type = 'text';
            input.className = 'folder-rename-input';
            input.value = folder.name;

            nameEl.innerHTML = '';
            nameEl.appendChild(input);
            input.focus();
            input.select();

            function commit() {
                const newName = input.value.trim();
                if (newName && newName !== folder.name) {
                    renameFolder(folderId, newName);
                } else {
                    renderFolderGrid(); // restore original
                }
            }

            input.addEventListener('blur', commit);
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    input.blur();
                } else if (e.key === 'Escape') {
                    input.value = folder.name; // cancel
                    input.blur();
                }
            });
        }

        function renderFolderDetailSessions(folder) {
            const container = document.getElementById('folderDetailSessions');
            if (!container) return;

            if (folder.sessionIds.length === 0) {
                container.innerHTML = '<div class="folder-detail-empty">此資料夾尚無搜尋記錄</div>';
                return;
            }

            // Match sessionIds to savedSessions
            const sessions = folder.sessionIds
                .map(id => savedSessions.find(s => s.id === id))
                .filter(Boolean);

            if (sessions.length === 0) {
                container.innerHTML = '<div class="folder-detail-empty">此資料夾尚無搜尋記錄</div>';
                return;
            }

            container.innerHTML = sessions.map(session => {
                const dateStr = getTimeAgo(session.updatedAt || session.createdAt);
                return `
                    <div class="folder-session-item" data-session-id="${session.id}">
                        <div class="folder-session-info">
                            <div class="folder-session-title">${escapeHTML(session.title)}</div>
                            <div class="folder-session-meta">更新時間 ${dateStr}</div>
                        </div>
                        <button class="folder-session-remove-btn" data-remove-session-id="${session.id}" title="從資料夾移除">&times;</button>
                    </div>
                `;
            }).join('');

            // Click session → load it (ignore remove button clicks)
            container.querySelectorAll('.folder-session-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    if (e.target.closest('.folder-session-remove-btn')) return;
                    const sessionId = parseInt(item.dataset.sessionId);
                    const session = savedSessions.find(s => s.id === sessionId);
                    if (session) {
                        // 切換前先保存當前對話（防止深度報告等狀態丟失）
                        if (sessionHistory.length > 0 || currentResearchReport) {
                            saveCurrentSession();
                        }
                        hideFolderPage();
                        loadSavedSession(session);
                    }
                });
            });

            // Remove session from folder
            container.querySelectorAll('.folder-session-remove-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const sessionId = parseInt(btn.dataset.removeSessionId);
                    removeSessionFromFolder(folder.id, sessionId);
                    // Re-render with updated folder data
                    const updatedFolder = folders.find(f => f.id === folder.id);
                    if (updatedFolder) {
                        renderFolderDetailSessions(updatedFolder);
                    }
                    console.log(`[Folder] Session ${sessionId} removed from folder ${folder.id}`);
                });
            });
        }

        // -- Wire sidebar "開啟資料夾" button to folder page --
        btnToggleCategories.addEventListener('click', () => {
            showFolderPage();
        });

        // "< 回到搜尋" button on folder main page
        document.getElementById('btnFolderBackToHome').addEventListener('click', () => {
            hideFolderPage();
        });

        // "新增資料夾" button on folder page
        document.getElementById('btnAddFolder').addEventListener('click', () => {
            createFolder();
        });

        // "< 回到頁" button
        document.getElementById('btnFolderBack').addEventListener('click', () => {
            showFolderMain();
        });

        // Folder search input
        document.getElementById('folderSearchInput').addEventListener('input', (e) => {
            currentFolderFilter = e.target.value.trim();
            renderFolderGrid();
        });

        // Folder sort tabs
        document.querySelectorAll('.folder-sort-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.folder-sort-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                currentFolderSort = tab.dataset.sort;
                renderFolderGrid();
            });
        });

        // -- Drag-and-drop: sidebar sessions → folder cards --
        // 使用 event delegation 避免 listener 堆疊，且不干擾子元素點擊

        // 單一 delegated handler，綁在 container 上（只綁一次）
        (function initSidebarDragDelegation() {
            const container = document.getElementById('leftSidebarSessions');
            if (!container) return;

            container.addEventListener('dragstart', (e) => {
                if (!_folderModeActive) return;
                // 若從按鈕/選單觸發，取消拖曳
                if (e.target.closest('.left-sidebar-session-menu-btn') || e.target.closest('.left-sidebar-session-dropdown')) {
                    e.preventDefault();
                    return;
                }
                const item = e.target.closest('.left-sidebar-session-item');
                if (!item) return;
                const sessionId = item.dataset.sidebarSessionId;
                if (!sessionId) return;
                e.dataTransfer.setData('text/session-id', sessionId);
                e.dataTransfer.effectAllowed = 'copy';
                item.classList.add('dragging');
            });

            container.addEventListener('dragend', (e) => {
                const item = e.target.closest('.left-sidebar-session-item');
                if (item) item.classList.remove('dragging');
            });
        })();

        function makeSidebarSessionsDraggable() {
            document.querySelectorAll('.left-sidebar-session-item').forEach(item => {
                item.setAttribute('draggable', 'true');
            });
        }

        function removeSidebarSessionsDraggable() {
            document.querySelectorAll('.left-sidebar-session-item').forEach(item => {
                item.removeAttribute('draggable');
                item.classList.remove('dragging');
            });
        }

        // ==================== END FOLDER/PROJECT SYSTEM ====================

        // ==================== LARGE FONT MODE ====================
        (function initLargeFontMode() {
            document.addEventListener('DOMContentLoaded', () => {
                const btn = document.getElementById('btnFontSize');
                if (!btn) return;

                // Restore preference
                try {
                    if (localStorage.getItem('nlweb-large-font') === 'true') {
                        document.body.classList.add('large-font');
                        btn.classList.add('active');
                    }
                } catch (e) { /* localStorage unavailable */ }

                btn.addEventListener('click', () => {
                    const isActive = document.body.classList.toggle('large-font');
                    btn.classList.toggle('active', isActive);
                    try {
                        localStorage.setItem('nlweb-large-font', isActive ? 'true' : 'false');
                    } catch (e) { /* localStorage unavailable */ }
                });
            });
        })();

        // ==================== KG VISIBILITY TOGGLE ====================
        (function initKGVisibilityToggle() {
            document.addEventListener('DOMContentLoaded', () => {
                const hideBtn = document.getElementById('kgHideBtn');
                const restoreBar = document.getElementById('kgRestoreBar');
                const kgContainer = document.getElementById('kgDisplayContainer');
                if (!hideBtn || !restoreBar || !kgContainer) return;

                // Restore preference
                let kgHidden = false;
                try {
                    kgHidden = localStorage.getItem('nlweb-kg-hidden') === 'true';
                } catch (e) { /* localStorage unavailable */ }

                // Apply stored preference: if hidden, ensure container stays hidden and bar is ready
                if (kgHidden) {
                    // The container starts display:none anyway; keep restoreBar ready
                    // restoreBar will show when displayKnowledgeGraph is called
                    kgContainer.dataset.userHidden = 'true';
                }

                hideBtn.addEventListener('click', () => {
                    kgContainer.style.display = 'none';
                    kgContainer.dataset.userHidden = 'true';
                    restoreBar.style.display = 'block';
                    try {
                        localStorage.setItem('nlweb-kg-hidden', 'true');
                    } catch (e) {}
                });

                restoreBar.addEventListener('click', () => {
                    kgContainer.style.display = 'block';
                    kgContainer.dataset.userHidden = 'false';
                    restoreBar.style.display = 'none';
                    try {
                        localStorage.setItem('nlweb-kg-hidden', 'false');
                    } catch (e) {}
                });
            });
        })();

        // Initialize on page load
        document.addEventListener('DOMContentLoaded', () => {
            loadUserFiles();
            loadSiteFilters();
            initPinnedBanner();
        });

