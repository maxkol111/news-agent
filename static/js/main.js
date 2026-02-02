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
function trackTaskProgress(taskId, onComplete, onError) {
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
            }
        } catch (error) {
            console.error('Task tracking error:', error);
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

// Инициализация при загрузке страницы
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
    
    // Обновление статуса системы
    updateSystemStatus();
    setInterval(updateSystemStatus, 30000);
});

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

// Экспорт функций в глобальную область видимости
window.showNotification = showNotification;
window.apiRequest = apiRequest;
window.searchNews = searchNews;
window.collectNews = collectNews;
window.analyzeTopic = analyzeTopic;
window.trackTaskProgress = trackTaskProgress;
window.formatDate = formatDate;
window.truncateText = truncateText;