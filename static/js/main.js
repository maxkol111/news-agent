// Активация соответствующих элементов при загрузке
$(document).ready(function() {
    // Активируем вкладку если указана - ИСПРАВЛЕНО: используем data-target вместо data-tab
    const activeTab = '{{ active_tab or "" }}';
    console.log('Active tab from template:', activeTab);
    
    if (activeTab && activeTab !== 'home') {
        // Находим все вкладки и контент панелей
        const tabButtons = document.querySelectorAll('.nav-link[data-bs-toggle="tab"]');
        const tabPanes = document.querySelectorAll('.tab-pane');
        
        // Деактивируем все вкладки
        tabButtons.forEach(btn => {
            btn.classList.remove('active');
            btn.setAttribute('aria-selected', 'false');
        });
        
        // Деактивируем все панели
        tabPanes.forEach(pane => {
            pane.classList.remove('show', 'active');
        });
        
        // Активируем нужную вкладку
        const targetTab = document.querySelector(`[data-target="#${activeTab}Tab"]`);
        const targetPane = document.getElementById(`${activeTab}Tab`);
        
        if (targetTab) {
            targetTab.classList.add('active');
            targetTab.setAttribute('aria-selected', 'true');
        }
        
        if (targetPane) {
            targetPane.classList.add('show', 'active');
        }
    }
    
    // Автопрокрутка к блоку анализа если нужно - ИСПРАВЛЕНО: более точный селектор
    {% if show_analysis %}
    setTimeout(() => {
        // Ищем блок анализа по заголовку
        const analysisHeaders = document.querySelectorAll('.card-header');
        let analysisHeader = null;
        
        for (let header of analysisHeaders) {
            if (header.textContent.includes('Анализ темы') || 
                header.classList.contains('bg-warning')) {
                analysisHeader = header;
                break;
            }
        }
        
        if (analysisHeader) {
            analysisHeader.scrollIntoView({ 
                behavior: 'smooth', 
                block: 'start',
                inline: 'nearest'
            });
            
            // Также активируем поле ввода
            const topicInput = document.getElementById('topicInput');
            if (topicInput) {
                topicInput.focus();
                showNotification('Введите тему для анализа в поле выше', 'info', 3000);
            }
        }
    }, 800); // Увеличена задержка для полной загрузки
    {% endif %}
    
    // Заполняем поле поиска если есть запрос - ИСПРАВЛЕНО: добавлена проверка
    {% if search_query %}
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.value = '{{ search_query }}';
        
        // Автоматически выполняем поиск если запрос не пустой
        if ('{{ search_query }}'.trim().length > 0) {
            setTimeout(() => {
                performSearch();
            }, 1000);
        }
    }
    {% endif %}
    
    // Инициализируем загрузку данных с учетом активной вкладки
    initializePageData();
});

/**
 * Инициализация данных страницы в зависимости от активной вкладки
 */
function initializePageData() {
    // Проверяем, какая вкладка активна
    const activePane = document.querySelector('.tab-pane.show.active');
    const activeTabId = activePane ? activePane.id : '';
    
    console.log('Active tab pane:', activeTabId);
    
    // Загружаем данные для всех вкладок или только для активной
    if (!activeTabId || activeTabId === 'homeTab' || activeTabId === 'newsTab') {
        loadLatestNews();
    }
    
    if (!activeTabId || activeTabId === 'homeTab') {
        loadLatestAnalyses();
        updateSystemStatus();
        
        // Обновляем статус каждые 30 секунд
        setInterval(updateSystemStatus, 30000);
    }
    
    // Если активна вкладка анализа, фокусируемся на поле ввода
    if (activeTabId === 'analyzeTab') {
        setTimeout(() => {
            const topicInput = document.getElementById('topicInput');
            if (topicInput) {
                topicInput.focus();
            }
        }, 500);
    }
    
    // Если активна вкладка поиска, фокусируемся на поле поиска
    if (activeTabId === 'searchTab') {
        setTimeout(() => {
            const searchInput = document.getElementById('searchInput');
            if (searchInput) {
                searchInput.focus();
            }
        }, 500);
    }
}

/**
 * Функция для переключения вкладок через JavaScript
 */
function switchTab(tabName) {
    const tabButton = document.querySelector(`[data-target="#${tabName}Tab"]`);
    if (tabButton) {
        // Используем Bootstrap для переключения вкладок
        const tab = new bootstrap.Tab(tabButton);
        tab.show();
        
        // Обновляем URL без перезагрузки страницы
        history.pushState(null, '', `/${tabName === 'home' ? '' : tabName}`);
        
        // Инициализируем данные для новой вкладки
        setTimeout(() => initializePageData(), 300);
    }
}

/**
 * Основной JavaScript файл для новостного агента
 */

// Глобальные переменные
let currentTask = null;

// Функции уведомлений
function showNotification(message, type = 'info', duration = 5000) {
    const notificationArea = document.getElementById('notificationArea');
    if (!notificationArea) return;
    
    const alertClass = {
        'success': 'alert-success',
        'error': 'alert-danger',
        'warning': 'alert-warning',
        'info': 'alert-info'
    }[type] || 'alert-info';
    
    const notificationId = 'notification-' + Date.now();
    const notification = `
        <div id="${notificationId}" class="alert ${alertClass} alert-dismissible fade show" role="alert">
            <div class="d-flex align-items-center">
                <i class="bi ${getNotificationIcon(type)} me-2"></i>
                <div>${message}</div>
            </div>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    notificationArea.insertAdjacentHTML('beforeend', notification);
    
    // Автоматическое скрытие
    if (duration > 0) {
        setTimeout(() => {
            const alert = document.getElementById(notificationId);
            if (alert) {
                alert.classList.remove('show');
                setTimeout(() => alert.remove(), 150);
            }
        }, duration);
    }
}

function getNotificationIcon(type) {
    const icons = {
        'success': 'bi-check-circle-fill',
        'error': 'bi-exclamation-triangle-fill',
        'warning': 'bi-exclamation-circle-fill',
        'info': 'bi-info-circle-fill'
    };
    return icons[type] || 'bi-info-circle-fill';
}

// Функции работы с API
async function apiRequest(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        if (data && (method === 'POST' || method === 'PUT')) {
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(endpoint, options);
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || `HTTP ${response.status}`);
        }
        
        return result;
    } catch (error) {
        console.error('API Error:', error);
        showNotification(`Ошибка API: ${error.message}`, 'error');
        throw error;
    }
}

// Функции для работы с новостями
async function searchNews(query, limit = 20) {
    try {
        const url = `/api/search?q=${encodeURIComponent(query)}&limit=${limit}`;
        return await apiRequest(url);
    } catch (error) {
        return { success: false, results: [] };
    }
}

async function collectNews(limit = 3) {
    try {
        return await apiRequest('/api/collect', 'POST', { limit });
    } catch (error) {
        return { success: false };
    }
}

async function analyzeTopic(topic) {
    try {
        return await apiRequest('/api/analyze', 'POST', { topic });
    } catch (error) {
        return { success: false };
    }
}

// Функции для отслеживания задач
function trackTaskProgress(taskId, onComplete, onError, onProgress = null) {
    if (currentTask) {
        clearInterval(currentTask);
    }
    
    currentTask = setInterval(async () => {
        try {
            const task = await apiRequest(`/api/task/${taskId}`);
            
            if (task.status === 'completed') {
                clearInterval(currentTask);
                currentTask = null;
                if (onComplete) onComplete(task.result);
            } else if (task.status === 'error') {
                clearInterval(currentTask);
                currentTask = null;
                if (onError) onError(task.error);
            } else if (task.status === 'running' && onProgress) {
                onProgress(task.progress || 0);
            }
        } catch (error) {
            console.error('Task tracking error:', error);
            // Не очищаем интервал при временных ошибках
        }
    }, 1000);
}

// Функции для форматирования
function formatDate(dateString) {
    if (!dateString) return '';
    
    try {
        const date = new Date(dateString);
        return date.toLocaleDateString('ru-RU', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (error) {
        return dateString;
    }
}

function truncateText(text, maxLength = 100) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

// Загрузка последних новостей
function loadLatestNews() {
    const newsContainer = document.getElementById('latestNews');
    if (!newsContainer) return;
    
    $.get('/api/search?limit=5', function(data) {
        if (data.success && data.results.length > 0) {
            let html = '';
            data.results.forEach(news => {
                html += `
                    <div class="news-item mb-3">
                        <div class="d-flex justify-content-between align-items-start">
                            <h6 class="mb-1">
                                <a href="${news.url}" target="_blank" class="text-decoration-none">${news.title}</a>
                            </h6>
                            <span class="badge ${news.category_color}">${news.category}</span>
                        </div>
                        <p class="mb-1 text-muted small">
                            <i class="bi bi-newspaper"></i> ${news.source} • 
                            <i class="bi bi-clock"></i> ${news.published}
                        </p>
                        ${news.summary ? `<p class="small">${news.summary}</p>` : ''}
                        <hr>
                    </div>
                `;
            });
            $('#latestNews').html(html);
        } else {
            $('#latestNews').html(`
                <div class="text-center py-4">
                    <i class="bi bi-inbox display-4 text-muted"></i>
                    <p class="mt-2">Новостей пока нет</p>
                    <button class="btn btn-sm btn-outline-primary" onclick="collectNewsModal()">
                        <i class="bi bi-cloud-download"></i> Собрать новости
                    </button>
                </div>
            `);
        }
    });
}

// Загрузка последних анализов
function loadLatestAnalyses() {
    const analysesContainer = document.getElementById('latestAnalyses');
    if (!analysesContainer) return;
    
    $.get('/api/statistics/detailed', function(data) {
        if (data.success && data.recent_analyses && data.recent_analyses.length > 0) {
            let html = '<div class="list-group">';
            data.recent_analyses.slice(0, 3).forEach(analysis => {
                html += `
                    <div class="list-group-item">
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1">${analysis.query || 'Анализ'}</h6>
                            <small>${analysis.created_at ? analysis.created_at.slice(0, 10) : ''}</small>
                        </div>
                        <small class="text-muted">Нажмите для просмотра полного анализа</small>
                    </div>
                `;
            });
            html += '</div>';
            $('#latestAnalyses').html(html);
        } else {
            $('#latestAnalyses').html(`
                <div class="text-center py-3">
                    <i class="bi bi-graph-up display-4 text-muted"></i>
                    <p class="mt-2">Анализов пока нет</p>
                    <button class="btn btn-sm btn-outline-warning" onclick="switchTab('analyze')">
                        <i class="bi bi-graph-up"></i> Создать анализ
                    </button>
                </div>
            `);
        }
    });
}

// Обновление статуса системы
async function updateSystemStatus() {
    try {
        const status = await apiRequest('/api/status');
        const indicator = document.getElementById('statusIndicator');
        
        if (indicator) {
            if (status.error) {
                indicator.innerHTML = `
                    <i class="bi bi-circle-fill text-danger"></i>
                    <span class="ms-1">Ошибка: ${status.error}</span>
                `;
            } else {
                const newsCount = status.statistics?.total_news || 0;
                indicator.innerHTML = `
                    <i class="bi bi-circle-fill text-success"></i>
                    <span class="ms-1">Система активна (${newsCount} новостей)</span>
                `;
            }
        }
    } catch (error) {
        console.error('Status update error:', error);
    }
}

// Функция для выполнения поиска (если используется)
function performSearch() {
    const searchInput = document.getElementById('searchInput');
    if (!searchInput) return;
    
    const query = searchInput.value.trim();
    if (query.length === 0) return;
    
    // Редирект на страницу поиска или выполнение поиска на месте
    window.location.href = `/search?q=${encodeURIComponent(query)}`;
}

// Функция для открытия модального окна сбора новостей
function collectNewsModal() {
    $('#collectModal').modal('show');
}

// Инициализация Bootstrap компонентов
document.addEventListener('DOMContentLoaded', function() {
    // Инициализация тултипов
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Инициализация поповеров
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
});

// Экспорт функций в глобальную область видимости
window.showNotification = showNotification;
window.apiRequest = apiRequest;
window.searchNews = searchNews;
window.collectNews = collectNews;
window.analyzeTopic = analyzeTopic;
window.trackTaskProgress = trackTaskProgress;
window.formatDate = formatDate;
window.truncateText = truncateText;
window.switchTab = switchTab;
window.loadLatestNews = loadLatestNews;
window.loadLatestAnalyses = loadLatestAnalyses;
window.updateSystemStatus = updateSystemStatus;
window.performSearch = performSearch;
window.collectNewsModal = collectNewsModal;