#!/usr/bin/env python3
"""
ВЕБ-ИНТЕРФЕЙС ДЛЯ НОВОСТНОГО ИИ-АГЕНТА
Flask приложение с полноценным UI
"""

import os
import sys
import json
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, render_template_string
from flask_cors import CORS

# Добавляем текущую директорию в путь для импорта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Импортируем нашего агента
try:
    from news_agent_v2 import NewsAgentV2
    AGENT_AVAILABLE = True
    print("✅ Агент news_agent_v2.py доступен")
except ImportError as e:
    print(f"⚠️  Ошибка импорта агента: {e}")
    AGENT_AVAILABLE = False
except Exception as e:
    print(f"⚠️  Другая ошибка при импорте агента: {e}")
    AGENT_AVAILABLE = False

# Создаем Flask приложение
app = Flask(__name__)
app.secret_key = os.urandom(24).hex()  # Генерируем случайный ключ
CORS(app)

# Глобальные переменные
agent = None
active_tasks = {}  # Словарь для отслеживания асинхронных задач

def init_agent():
    """Инициализация агента"""
    global agent
    try:
        if AGENT_AVAILABLE:
            print("🔄 Инициализация агента...")
            agent = NewsAgentV2()
            print("✅ Агент инициализирован для веб-интерфейса")
            
            # Тестируем получение статуса
            try:
                status = agent.get_statistics()
                print(f"📊 Начальная статистика: {status}")
            except Exception as e:
                print(f"⚠️  Не удалось получить начальную статистику: {e}")
            
            return True
        else:
            print("❌ Агент недоступен для импорта")
            return False
    except Exception as e:
        print(f"❌ Ошибка инициализации агента: {e}")
        import traceback
        traceback.print_exc()
        return False

# Инициализируем агента сразу при запуске
print("\n🔄 Инициализация веб-интерфейса...")
init_agent()

# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def format_datetime(dt_str):
    """Форматирование даты"""
    if not dt_str:
        return ""
    
    try:
        # Убираем временную зону если есть
        dt_str = dt_str.split('+')[0].split('Z')[0]
        
        # Пробуем разные форматы
        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%d.%m.%Y %H:%M']:
            try:
                dt = datetime.strptime(dt_str, fmt)
                return dt.strftime('%d.%m.%Y %H:%M')
            except:
                continue
        
        # Если не удалось распарсить, возвращаем как есть
        return str(dt_str)[:16]
    except:
        return str(dt_str)[:16] if dt_str else ""

def get_category_color(category):
    """Цвет для категории"""
    if not category:
        return 'secondary'
    
    colors = {
        'технологии': 'primary',
        'политика': 'danger',
        'экономика': 'warning',
        'наука': 'info',
        'спорт': 'success',
    }
    
    category_lower = category.lower().strip()
    for key in colors:
        if key in category_lower:
            return colors[key]
    
    return 'secondary'

def get_importance_badge(importance):
    """Бейдж важности"""
    if importance is None:
        importance = 0.5
    
    if importance >= 0.8:
        return '<span class="badge bg-danger">🔥 Высокая</span>'
    elif importance >= 0.6:
        return '<span class="badge bg-warning">⚠️ Средняя</span>'
    else:
        return '<span class="badge bg-secondary">📰 Низкая</span>'

def get_system_stats():
    """Получение статистики системы (общая функция для всех маршрутов)"""
    if not agent:
        # Демо-режим
        return {
            "statistics": {
                "total_news": 0,
                "analyzed_news": 0, 
                "total_analyses": 0,
                "analysis_coverage": "0%",
                "categories": {
                    "технологии": 0,
                    "политика": 0,
                    "экономика": 0,
                    "наука": 0,
                    "спорт": 0
                }
            },
            "database_size_mb": 0,
            "timestamp": datetime.now().isoformat()
        }
    
    try:
        return agent.get_statistics()
    except Exception as e:
        print(f"⚠️  Ошибка получения статистики: {e}")
        # Возвращаем базовую статистику при ошибке
        return {
            "statistics": {
                "total_news": 0,
                "analyzed_news": 0,
                "total_analyses": 0,
                "analysis_coverage": "0%",
                "categories": {}
            },
            "database_size_mb": 0,
            "timestamp": datetime.now().isoformat()
        }

# ============================================================================
# API МАРШРУТЫ
# ============================================================================

@app.route('/api/status')
def api_status():
    """API статуса агента"""
    if not agent:
        return jsonify({
            'success': False,
            'error': 'Агент не инициализирован',
            'agent_available': False,
            'demo_mode': True,
            'message': 'Работает в демо-режиме. Убедитесь что файл news_agent_v2.py в папке проекта.',
            'timestamp': datetime.now().isoformat()
        })
    
    try:
        status = agent.get_statistics()
        return jsonify({
            'success': True,
            'agent_available': True,
            **status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'agent_available': True,
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/collect', methods=['POST'])
def api_collect():
    """API сбора новостей"""
    if not agent:
        return jsonify({
            'success': False,
            'error': 'Агент не инициализирован',
            'demo_mode': True,
            'message': 'В демо-режиме сбор новостей не доступен'
        })
    
    try:
        data = request.json or {}
        limit = data.get('limit', 3)
        
        task_id = f"collect_{datetime.now().timestamp()}"
        
        def collect_task():
            try:
                active_tasks[task_id] = {'status': 'running', 'progress': 0}
                print(f"🔄 Задача {task_id}: Начало сбора новостей...")
                agent.collect_news(limit_per_source=limit)
                active_tasks[task_id] = {'status': 'completed', 'progress': 100}
                print(f"✅ Задача {task_id}: Сбор новостей завершен")
            except Exception as e:
                print(f"❌ Задача {task_id}: Ошибка сбора новостей: {e}")
                active_tasks[task_id] = {'status': 'error', 'error': str(e)}
        
        thread = threading.Thread(target=collect_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f'Сбор новостей запущен (лимит: {limit} с каждого источника)'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """API анализа темы"""
    if not agent:
        return jsonify({
            'success': False,
            'error': 'Агент не инициализирован',
            'demo_mode': True,
            'message': 'В демо-режиме анализ не доступен'
        })
    
    try:
        data = request.json or {}
        if not data.get('topic'):
            return jsonify({
                'success': False,
                'error': 'Тема не указана'
            })
        
        topic = data['topic']
        task_id = f"analyze_{datetime.now().timestamp()}"
        
        def analyze_task():
            try:
                active_tasks[task_id] = {'status': 'running', 'progress': 0}
                print(f"🔄 Задача {task_id}: Начало анализа темы '{topic}'...")
                result = agent.analyze_topic(topic)
                active_tasks[task_id] = {'status': 'completed', 'result': result}
                print(f"✅ Задача {task_id}: Анализ темы завершен")
            except Exception as e:
                print(f"❌ Задача {task_id}: Ошибка анализа: {e}")
                active_tasks[task_id] = {'status': 'error', 'error': str(e)}
        
        thread = threading.Thread(target=analyze_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f'Анализ темы "{topic}" запущен'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/search')
def api_search():
    """API поиска новостей"""
    if not agent:
        # Демо-режим
        query = request.args.get('q', '')
        limit = min(int(request.args.get('limit', 10)), 50)
        
        demo_results = [
            {
                'id': 1,
                'title': 'Пример: Искусственный интеллект в медицине',
                'content': 'Новые алгоритмы ИИ показывают высокую точность в диагностике заболеваний...',
                'summary': 'Прорыв в медицинском ИИ',
                'source': 'Демо-источник',
                'url': '#',
                'category': 'технологии',
                'published': datetime.now().isoformat(),
                'importance': 0.8
            },
            {
                'id': 2,
                'title': 'Пример: Экономические новости',
                'content': 'Центробанк опубликовал новые данные...',
                'summary': 'Стабильность экономики',
                'source': 'Демо-источник 2',
                'url': '#',
                'category': 'экономика',
                'published': datetime.now().isoformat(),
                'importance': 0.6
            }
        ]
        
        # Фильтруем по запросу
        filtered_results = []
        for item in demo_results:
            if (not query or 
                query.lower() in item['title'].lower() or 
                query.lower() in item['category'].lower()):
                filtered_results.append(item)
        
        # Форматируем результаты
        formatted_results = []
        for news in filtered_results[:limit]:
            formatted_news = {
                'id': news.get('id', 0),
                'title': news.get('title', ''),
                'content': news.get('content', ''),
                'summary': news.get('summary', ''),
                'source': news.get('source', ''),
                'url': news.get('url', '#'),
                'category': news.get('category', 'разное'),
                'category_color': get_category_color(news.get('category', 'разное')),
                'published': format_datetime(news.get('published', '')),
                'importance': news.get('importance', 0.5),
                'importance_badge': get_importance_badge(news.get('importance', 0.5))
            }
            formatted_results.append(formatted_news)
        
        return jsonify({
            'success': True,
            'demo_mode': True,
            'query': query,
            'results': formatted_results,
            'count': len(formatted_results)
        })
    
    try:
        query = request.args.get('q', '')
        limit = min(int(request.args.get('limit', 20)), 50)
        
        results = agent.search_news(query, limit=limit)
        
        # Форматируем результаты для веб-интерфейса
        formatted_results = []
        for news in results:
            formatted_news = {
                'id': news.get('id', 0),
                'title': news.get('title', ''),
                'content': news.get('content', ''),
                'summary': news.get('summary', ''),
                'source': news.get('source', ''),
                'url': news.get('url', '#'),
                'category': news.get('category', 'разное'),
                'category_color': get_category_color(news.get('category', 'разное')),
                'published': format_datetime(news.get('published', '')),
                'importance': news.get('importance', 0.5),
                'importance_badge': get_importance_badge(news.get('importance', 0.5))
            }
            formatted_results.append(formatted_news)
        
        return jsonify({
            'success': True,
            'query': query,
            'results': formatted_results,
            'count': len(formatted_results)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/task/<task_id>')
def api_task_status(task_id):
    """API статуса задачи - ВАЖНО: этот маршрут нужен для отслеживания прогресса анализа"""
    task = active_tasks.get(task_id)
    if not task:
        return jsonify({
            'success': False,
            'error': 'Задача не найдена'
        }), 404
    
    return jsonify({
        'success': True,
        **task
    })

@app.route('/api/statistics/detailed')
def api_detailed_statistics():
    """API детальной статистики - для совместимости с фронтендом"""
    if not agent:
        return jsonify({
            'success': False,
            'error': 'Агент не инициализирован',
            'recent_analyses': []
        })
    
    try:
        # Пытаемся получить детальную статистику или возвращаем пустую
        stats = agent.get_statistics()
        return jsonify({
            'success': True,
            'recent_analyses': []
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'recent_analyses': []
        })

# ============================================================================
# КОНТЕКСТНЫЕ ПРОЦЕССОРЫ
# ============================================================================

@app.context_processor
def utility_processor():
    """Добавляем функции в контекст шаблонов"""
    def category_color(category):
        return get_category_color(category)
    
    return dict(get_category_color=category_color, now=datetime.now)

# ============================================================================
# ВЕБ-МАРШРУТЫ (ИСПРАВЛЕНЫ - ВСЕ ВОЗВРАЩАЮТ СТАТИСТИКУ)
# ============================================================================

@app.route('/')
def index():
    """Главная страница"""
    try:
        stats = get_system_stats()
        return render_template('index.html', stats=stats, active_tab='home')
    except Exception as e:
        # Если шаблон не найден, показываем простую страницу
        return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Ошибка</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            </head>
            <body>
                <div class="container mt-5">
                    <div class="alert alert-danger">
                        <h1>Ошибка загрузки шаблона</h1>
                        <p>Не удалось загрузить шаблон index.html</p>
                        <pre>%s</pre>
                        <a href="/api/status" class="btn btn-primary">Проверить API</a>
                    </div>
                </div>
            </body>
            </html>
        ''' % str(e))

@app.route('/news')
def news_page():
    """Страница новостей - рендерим главную с активированной вкладкой новостей"""
    try:
        stats = get_system_stats()
        return render_template('index.html', stats=stats, active_tab='news')
    except:
        # Если ошибка, редиректим на главную
        return redirect('/')

@app.route('/analyze')
def analyze_page():
    """Страница анализа - рендерим главную с активированным блоком анализа"""
    try:
        stats = get_system_stats()
        return render_template('index.html', stats=stats, active_tab='analyze', show_analysis=True)
    except:
        # Если ошибка, редиректим на главную
        return redirect('/')

@app.route('/statistics')
def statistics_page():
    """Страница статистики - рендерим главную с активированной вкладкой статистики"""
    try:
        stats = get_system_stats()
        return render_template('index.html', stats=stats, active_tab='statistics')
    except:
        # Если ошибка, редиректим на главную
        return redirect('/')

@app.route('/search')
def search_page():
    """Страница поиска - рендерим главную с активированным поиском"""
    try:
        query = request.args.get('q', '')
        stats = get_system_stats()
        return render_template('index.html', stats=stats, active_tab='search', search_query=query)
    except:
        # Если ошибка, редиректим на главную
        return redirect('/')

# ============================================================================
# СТАТИЧЕСКИЕ ФАЙЛЫ
# ============================================================================

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Сервировка статических файлов"""
    try:
        return send_file(os.path.join('static', filename))
    except:
        return "Файл не найден", 404

# ============================================================================
# ОБРАБОТКА ОШИБОК
# ============================================================================

@app.errorhandler(404)
def not_found_error(error):
    """Обработка 404 ошибки"""
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>404 - Страница не найдена</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body>
            <div class="container mt-5">
                <div class="alert alert-danger">
                    <h1><i class="bi bi-exclamation-triangle"></i> 404 - Страница не найдена</h1>
                    <p>Запрошенная страница не существует.</p>
                    <a href="/" class="btn btn-primary">На главную</a>
                </div>
            </div>
        </body>
        </html>
    '''), 404

@app.errorhandler(500)
def internal_error(error):
    """Обработка 500 ошибки"""
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>500 - Ошибка сервера</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body>
            <div class="container mt-5">
                <div class="alert alert-danger">
                    <h1><i class="bi bi-exclamation-triangle"></i> 500 - Внутренняя ошибка сервера</h1>
                    <p>Произошла непредвиденная ошибка.</p>
                    <pre>{}</pre>
                    <a href="/" class="btn btn-primary">На главную</a>
                </div>
            </div>
        </body>
        </html>
    '''.format(str(error))), 500

# ============================================================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# ============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("🌐 ЗАПУСК ВЕБ-ИНТЕРФЕЙСА НОВОСТНОГО АГЕНТА")
    print("=" * 60)
    
    # Проверяем структуру папок
    required_dirs = ['templates', 'static/css', 'static/js', 'static/images']
    for dir_path in required_dirs:
        os.makedirs(dir_path, exist_ok=True)
        print(f"📁 Проверена папка: {dir_path}")
    
    if agent:
        print("✅ Агент готов к работе")
        try:
            stats = agent.get_statistics()
            print(f"📊 Статистика: {stats}")
        except Exception as e:
            print(f"⚠️  Не удалось получить статистику: {e}")
    else:
        print("⚠️  Агент не инициализирован, работа в демо-режиме")
        print("   Убедитесь что:")
        print("   1. Файл news_agent_v2.py в папке проекта")
        print("   2. Ollama запущен: ollama serve")
        print("   3. Модель скачана: ollama pull llama3.1:8b")
    
    print("\n🌍 Доступные маршруты:")
    print("   • http://localhost:5000/ - Главная страница (все функции)")
    print("   • http://localhost:5000/news - Новости (с активированной вкладкой)")
    print("   • http://localhost:5000/analyze - Анализ (с активированным блоком)")
    print("   • http://localhost:5000/statistics - Статистика (с активированной вкладкой)")
    print("   • http://localhost:5000/search - Поиск (с заполненным запросом)")
    print("   • http://localhost:5000/api/status - API статуса")
    print("   • http://localhost:5000/api/analyze - API анализа темы (POST)")
    print("   • http://localhost:5000/api/task/<id> - Статус задачи")
    print("\n📊 Статус системы передается на ВСЕХ маршрутах!")
    print("\n🚀 Запуск сервера...")
    print("=" * 60)
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=True, threaded=True, use_reloader=False)
    except Exception as e:
        print(f"❌ Ошибка запуска сервера: {e}")
        print("\n🔧 Возможные решения:")
        print("1. Порт 5000 может быть занят. Измените порт: app.run(port=5001)")
        print("2. Проверьте права доступа")
        print("3. Перезапустите терминал с правами администратора")