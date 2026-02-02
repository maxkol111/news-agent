#!/usr/bin/env python3
"""
НОВОСТНОЙ АГЕНТ V2.0
Полностью автономный - без внешних зависимостей кроме Ollama
"""

import os
import sys
import json
import sqlite3
import requests
import feedparser
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import hashlib
import re

class NewsAgentV2:
    """Автономный новостной агент с SQLite базой"""
    
    def __init__(self, model_name: str = "llama3.1:8b"):
        """
        Инициализация автономного агента
        
        Args:
            model_name: Название модели Ollama
        """
        print("=" * 70)
        print("🤖 АВТОНОМНЫЙ НОВОСТНОЙ АГЕНТ v2.0")
        print("=" * 70)
        
        self.model_name = model_name
        self.ollama_url = "http://localhost:11434"
        self.db_file = "news_agent_v2.db"
        self.session = requests.Session()
        
        # Настройки
        self.settings = {
            "rss_sources": [
                ("https://lenta.ru/rss/news", "Лента.ру"),
                ("https://ria.ru/export/rss2/index.xml", "РИА Новости"),
                ("https://tass.ru/rss/v2.xml", "ТАСС"),
                ("https://www.rbc.ru/rssfeed/newsline.rss", "РБК"),
            ],
            "categories": {
                "технологии": ["ии", "искусственный интеллект", "ai", "нейросеть", "чат", "gpt", "программирование", "it"],
                "политика": ["путин", "правительство", "сша", "украин", "санкци", "выборы", "политика"],
                "экономика": ["рубль", "доллар", "биржа", "инфляция", "экономика", "рынок", "кризис"],
                "наука": ["наука", "открытие", "исследование", "ученые", "космос", "медицина"],
                "спорт": ["спорт", "футбол", "хоккей", "чемпионат", "олимпиада"],
            }
        }
        
        # Инициализация
        self._init_database()
        self._check_ollama()
        
        print(f"\n✅ Агент инициализирован:")
        print(f"   • Модель: {self.model_name}")
        print(f"   • База данных: {self.db_file}")
        print(f"   • Источников RSS: {len(self.settings['rss_sources'])}")
    
    def _init_database(self):
        """Инициализация базы данных SQLite"""
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        
        # Таблица новостей
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT UNIQUE,
                title TEXT NOT NULL,
                content TEXT,
                summary TEXT,
                source TEXT,
                url TEXT,
                category TEXT,
                keywords TEXT,
                importance REAL DEFAULT 0.5,
                published TEXT,
                collected_at TEXT,
                analyzed_at TEXT
            )
        ''')
        
        # Таблица анализов
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                analysis TEXT,
                keywords TEXT,
                sources_used TEXT,
                created_at TEXT
            )
        ''')
        
        # Таблица статистики
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS stats (
                date TEXT PRIMARY KEY,
                news_collected INTEGER DEFAULT 0,
                news_analyzed INTEGER DEFAULT 0,
                analyses_made INTEGER DEFAULT 0
            )
        ''')
        
        # Индексы для быстрого поиска
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_title ON news(title)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_category ON news(category)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_published ON news(published)')
        
        self.conn.commit()
        
        # Создаем таблицу настроек если ее нет
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        # Сохраняем настройки
        self.cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value)
            VALUES ('model_name', ?)
        ''', (self.model_name,))
        
        self.conn.commit()
        print("💾 База данных инициализирована")
    
    def _check_ollama(self):
        """Проверка подключения к Ollama"""
        print("\n1. Проверка подключения к Ollama...")
        
        try:
            response = self.session.get(f"{self.ollama_url}/api/tags", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                
                if models:
                    print(f"   ✅ Ollama доступен (моделей: {len(models)})")
                    
                    # Проверяем нужную модель
                    model_names = [m.get("name", "") for m in models]
                    
                    if self.model_name in model_names:
                        print(f"   ✅ Модель '{self.model_name}' доступна")
                    else:
                        print(f"   ⚠️  Модель '{self.model_name}' не найдена")
                        available = ", ".join(model_names[:3])
                        print(f"   Доступные: {available}...")
                        
                        # Предлагаем выбрать другую
                        if "llama3.1" in available.lower():
                            for name in model_names:
                                if "llama3.1" in name.lower():
                                    self.model_name = name
                                    print(f"   Использую: {self.model_name}")
                                    break
                        elif model_names:
                            self.model_name = model_names[0]
                            print(f"   Использую первую доступную: {self.model_name}")
                else:
                    print("   ⚠️  Нет доступных моделей")
                    print("   🔧 Скачайте модель: ollama pull llama3.1:8b")
            else:
                print(f"   ❌ Ошибка HTTP: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print("   ❌ Не удается подключиться к Ollama")
            print("   🔧 Убедитесь что Ollama запущен: ollama serve")
            sys.exit(1)
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            sys.exit(1)
    
    def _generate_hash(self, text: str) -> str:
        """Генерация хэша для уникальной идентификации"""
        return hashlib.md5(text.encode()).hexdigest()
    
    def _categorize_text(self, text: str) -> str:
        """Автоматическая категоризация текста"""
        text_lower = text.lower()
        
        for category, keywords in self.settings["categories"].items():
            for keyword in keywords:
                if keyword in text_lower:
                    return category
        
        return "разное"
    
    def _calculate_importance(self, title: str, source: str, category: str) -> float:
        """Расчет важности статьи (0.0 - 1.0)"""
        score = 0.0
        
        # Вес источника
        source_weights = {
            "РИА Новости": 0.8,
            "ТАСС": 0.8,
            "Лента.ру": 0.7,
            "РБК": 0.6,
        }
        score += source_weights.get(source, 0.5)
        
        # Важные ключевые слова в заголовке
        important_words = [
            "путин", "война", "кризис", "сша", "китай", 
            "прорыв", "революция", "катастрофа", "теракт"
        ]
        title_lower = title.lower()
        for word in important_words:
            if word in title_lower:
                score += 0.2
                break
        
        # Категория
        category_weights = {
            "политика": 0.3,
            "экономика": 0.2,
            "технологии": 0.2,
            "наука": 0.1,
        }
        score += category_weights.get(category, 0.0)
        
        return min(score, 1.0)
    
    def call_llm(self, prompt: str, max_tokens: int = 500) -> str:
        """
        Вызов языковой модели через Ollama API
        
        Args:
            prompt: Запрос
            max_tokens: Максимальное количество токенов
            
        Returns:
            Ответ модели
        """
        try:
            url = f"{self.ollama_url}/api/generate"
            
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": max_tokens,
                    "top_k": 40,
                    "top_p": 0.9,
                }
            }
            
            response = self.session.post(url, json=payload, timeout=120)
            
            if response.status_code == 200:
                data = response.json()
                response_text = data.get("response", "").strip()
                
                # Очистка ответа от лишних символов
                response_text = re.sub(r'\n+', '\n', response_text).strip()
                return response_text
            else:
                error_msg = f"Ошибка API ({response.status_code})"
                if response.status_code == 404:
                    error_msg += " - Модель не найдена"
                print(f"❌ {error_msg}")
                return f"[Ошибка: {error_msg}]"
                
        except requests.exceptions.Timeout:
            print("❌ Таймаут запроса к модели")
            return "[Ошибка: Таймаут]"
        except Exception as e:
            print(f"❌ Ошибка вызова LLM: {e}")
            return f"[Ошибка: {str(e)}]"
    
    def summarize_text(self, text: str, max_length: int = 150) -> str:
        """
        Суммаризация текста
        
        Args:
            text: Исходный текст
            max_length: Максимальная длина резюме
            
        Returns:
            Краткое резюме
        """
        if len(text) < 50:
            return text
        
        prompt = f"""Создай краткое резюме текста (1-2 предложения):

ТЕКСТ:
{text[:800]}

РЕЗЮМЕ:"""
        
        summary = self.call_llm(prompt, max_tokens=100)
        return summary[:max_length]
    
    def extract_keywords(self, text: str, max_keywords: int = 5) -> List[str]:
        """
        Извлечение ключевых слов
        
        Args:
            text: Исходный текст
            max_keywords: Максимальное количество ключевых слов
            
        Returns:
            Список ключевых слов
        """
        if len(text) < 20:
            return []
        
        prompt = f"""Извлеки {max_keywords} ключевых слов или фраз из текста.
Верни только слова через запятую, без объяснений.

ТЕКСТ:
{text[:500]}

КЛЮЧЕВЫЕ СЛОВА:"""
        
        response = self.call_llm(prompt, max_tokens=100)
        
        # Парсинг ответа
        keywords = []
        for item in response.split(','):
            item = item.strip()
            if item and len(item) > 1:
                keywords.append(item)
        
        return keywords[:max_keywords]
    
    def collect_news(self, limit_per_source: int = 3):
        """
        Сбор новостей из RSS-лент
        
        Args:
            limit_per_source: Максимальное количество новостей с каждого источника
        """
        print(f"\n📰 СБОР НОВОСТЕЙ")
        print("-" * 60)
        
        total_collected = 0
        
        for rss_url, source_name in self.settings["rss_sources"]:
            try:
                print(f"📡 {source_name}...")
                feed = feedparser.parse(rss_url)
                
                if not feed.entries:
                    print(f"   ⚠️  Нет статей в ленте")
                    continue
                
                source_collected = 0
                
                for entry in feed.entries[:limit_per_source]:
                    # Генерируем уникальный хэш
                    article_hash = self._generate_hash(
                        f"{entry.get('link', '')}{entry.get('title', '')}"
                    )
                    
                    # Проверяем, есть ли уже такая статья
                    self.cursor.execute(
                        "SELECT id FROM news WHERE hash = ?", 
                        (article_hash,)
                    )
                    if self.cursor.fetchone():
                        continue
                    
                    # Подготавливаем данные
                    title = entry.get('title', 'Без заголовка').strip()
                    content = entry.get('summary', entry.get('description', '')).strip()
                    url = entry.get('link', '')
                    published = entry.get('published', datetime.now().isoformat())
                    category = self._categorize_text(title)
                    
                    # Рассчитываем важность
                    importance = self._calculate_importance(title, source_name, category)
                    
                    # Сохраняем в базу
                    self.cursor.execute('''
                        INSERT INTO news 
                        (hash, title, content, source, url, category, importance, published, collected_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        article_hash,
                        title,
                        content,
                        source_name,
                        url,
                        category,
                        importance,
                        published,
                        datetime.now().isoformat()
                    ))
                    
                    source_collected += 1
                    total_collected += 1
                    
                    print(f"   ✓ {title[:50]}...")
                
                print(f"   📊 Собрано: {source_collected} статей")
                
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
        
        self.conn.commit()
        
        # Обновляем статистику
        today = datetime.now().strftime("%Y-%m-%d")
        self.cursor.execute('''
            INSERT OR REPLACE INTO stats (date, news_collected)
            VALUES (?, COALESCE((SELECT news_collected FROM stats WHERE date = ?), 0) + ?)
        ''', (today, today, total_collected))
        self.conn.commit()
        
        print(f"\n✅ ИТОГО собрано: {total_collected} новых статей")
    
    def analyze_news_articles(self, limit: int = 5):
        """
        Анализ необработанных новостей
        
        Args:
            limit: Максимальное количество новостей для анализа
        """
        print(f"\n🔍 АНАЛИЗ НОВОСТЕЙ")
        print("-" * 60)
        
        # Получаем необработанные новости
        self.cursor.execute('''
            SELECT id, title, content, source, category
            FROM news 
            WHERE analyzed_at IS NULL 
            ORDER BY importance DESC, published DESC 
            LIMIT ?
        ''', (limit,))
        
        articles = self.cursor.fetchall()
        
        if not articles:
            print("   ℹ️  Нет необработанных новостей")
            return
        
        print(f"   Найдено для анализа: {len(articles)} статей")
        
        analyzed_count = 0
        
        for article in articles:
            try:
                article_id, title, content, source, category = article
                
                print(f"   📄 Анализ: {title[:40]}...")
                
                # Генерируем резюме
                summary = self.summarize_text(f"{title}. {content}")
                
                # Извлекаем ключевые слова
                keywords = self.extract_keywords(f"{title} {content}")
                keywords_str = ", ".join(keywords)
                
                # Обновляем запись в базе
                self.cursor.execute('''
                    UPDATE news 
                    SET summary = ?, keywords = ?, analyzed_at = ?
                    WHERE id = ?
                ''', (
                    summary,
                    keywords_str,
                    datetime.now().isoformat(),
                    article_id
                ))
                
                analyzed_count += 1
                
                # Пауза между запросами
                import time
                time.sleep(1)
                
            except Exception as e:
                print(f"   ❌ Ошибка анализа статьи: {e}")
        
        self.conn.commit()
        
        # Обновляем статистику
        today = datetime.now().strftime("%Y-%m-%d")
        self.cursor.execute('''
            INSERT OR REPLACE INTO stats (date, news_analyzed)
            VALUES (?, COALESCE((SELECT news_analyzed FROM stats WHERE date = ?), 0) + ?)
        ''', (today, today, analyzed_count))
        self.conn.commit()
        
        print(f"\n✅ Проанализировано: {analyzed_count} статей")
    
    def analyze_topic(self, topic: str) -> Dict[str, Any]:
        """
        Глубокий анализ темы
        
        Args:
            topic: Тема для анализа
            
        Returns:
            Результаты анализа
        """
        print(f"\n🎯 АНАЛИЗ ТЕМЫ: {topic}")
        print("-" * 60)
        
        start_time = datetime.now()
        
        try:
            # Ищем релевантные новости
            relevant_news = self.search_news(topic, limit=5)
            
            # Формируем контекст
            context = ""
            if relevant_news:
                context_lines = []
                for i, news in enumerate(relevant_news[:3], 1):
                    context_lines.append(f"{i}. {news['title']} ({news['source']})")
                    if news.get('summary'):
                        context_lines.append(f"   {news['summary']}")
                context = "\n".join(context_lines)
            
            # Создаем промпт для анализа
            prompt = f"""Проведи глубокий анализ темы на основе предоставленного контекста.

ТЕМА ДЛЯ АНАЛИЗА: {topic}

КОНТЕКСТ ИЗ НОВОСТЕЙ:
{context if context else "Нет релевантных новостей в базе"}

СТРУКТУРА АНАЛИЗА:
1. ОСНОВНЫЕ АСПЕКТЫ ТЕМЫ
2. КЛЮЧЕВЫЕ ФАКТЫ И ТЕНДЕНЦИИ  
3. ВОЗМОЖНЫЕ ПРИЧИНЫ И СЛЕДСТВИЯ
4. ПЕРСПЕКТИВЫ И ПРОГНОЗЫ
5. ВЫВОДЫ И РЕКОМЕНДАЦИИ

АНАЛИЗ:"""
            
            print("🤔 Модель проводит анализ...")
            analysis = self.call_llm(prompt, max_tokens=1000)
            
            # Извлекаем ключевые слова из анализа
            keywords = self.extract_keywords(analysis)
            
            # Сохраняем анализ в базу
            self.cursor.execute('''
                INSERT INTO analyses (query, analysis, keywords, sources_used, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                topic,
                analysis,
                json.dumps(keywords, ensure_ascii=False),
                str(len(relevant_news)),
                datetime.now().isoformat()
            ))
            
            # Обновляем статистику
            today = datetime.now().strftime("%Y-%m-%d")
            self.cursor.execute('''
                INSERT OR REPLACE INTO stats (date, analyses_made)
                VALUES (?, COALESCE((SELECT analyses_made FROM stats WHERE date = ?), 0) + 1)
            ''', (today, today))
            
            self.conn.commit()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result = {
                "topic": topic,
                "analysis": analysis,
                "keywords": keywords,
                "relevant_news_count": len(relevant_news),
                "analysis_time_seconds": round(duration, 2),
                "success": True,
                "timestamp": end_time.isoformat()
            }
            
            print(f"✅ Анализ завершен за {duration:.1f} секунд")
            print(f"📊 Использовано новостей: {len(relevant_news)}")
            print(f"🔑 Ключевые слова: {', '.join(keywords[:5])}")
            
            return result
            
        except Exception as e:
            print(f"❌ Ошибка анализа: {e}")
            
            return {
                "topic": topic,
                "error": str(e),
                "success": False,
                "timestamp": datetime.now().isoformat()
            }
    
    def search_news(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Поиск новостей по запросу
        
        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов
            
        Returns:
            Список новостей
        """
        try:
            # Простой полнотекстовый поиск в SQLite
            query_lower = query.lower()
            
            self.cursor.execute('''
                SELECT title, content, summary, source, url, category, keywords, published
                FROM news 
                WHERE LOWER(title) LIKE ? 
                   OR LOWER(content) LIKE ? 
                   OR LOWER(category) LIKE ?
                   OR LOWER(keywords) LIKE ?
                ORDER BY importance DESC, published DESC
                LIMIT ?
            ''', (
                f'%{query_lower}%',
                f'%{query_lower}%',
                f'%{query_lower}%',
                f'%{query_lower}%',
                limit
            ))
            
            results = []
            for row in self.cursor.fetchall():
                results.append({
                    "title": row[0],
                    "content": row[1],
                    "summary": row[2],
                    "source": row[3],
                    "url": row[4],
                    "category": row[5],
                    "keywords": row[6],
                    "published": row[7]
                })
            
            return results
            
        except Exception as e:
            print(f"⚠️ Ошибка поиска: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Получение статистики
        
        Returns:
            Статистика
        """
        try:
            # Общая статистика
            self.cursor.execute("SELECT COUNT(*) FROM news")
            total_news = self.cursor.fetchone()[0]
            
            self.cursor.execute("SELECT COUNT(*) FROM news WHERE analyzed_at IS NOT NULL")
            analyzed_news = self.cursor.fetchone()[0]
            
            self.cursor.execute("SELECT COUNT(*) FROM analyses")
            total_analyses = self.cursor.fetchone()[0]
            
            # Статистика по категориям
            self.cursor.execute('''
                SELECT category, COUNT(*) as count
                FROM news
                GROUP BY category
                ORDER BY count DESC
            ''')
            categories = {}
            for row in self.cursor.fetchall():
                categories[row[0]] = row[1]
            
            # Последние новости
            self.cursor.execute('''
                SELECT title, source, published
                FROM news
                ORDER BY published DESC
                LIMIT 3
            ''')
            recent_news = []
            for row in self.cursor.fetchall():
                recent_news.append({
                    "title": row[0][:50] + "..." if len(row[0]) > 50 else row[0],
                    "source": row[1],
                    "published": row[2][:10] if row[2] else "N/A"
                })
            
            return {
                "status": "ready",
                "model": self.model_name,
                "statistics": {
                    "total_news": total_news,
                    "analyzed_news": analyzed_news,
                    "total_analyses": total_analyses,
                    "analysis_coverage": f"{(analyzed_news/total_news*100):.1f}%" if total_news > 0 else "0%",
                    "categories": categories,
                },
                "recent_news": recent_news,
                "database_size_mb": os.path.getsize(self.db_file) / (1024 * 1024) if os.path.exists(self.db_file) else 0,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# ============================================================================
# ТЕРМИНАЛЬНЫЙ ИНТЕРФЕЙС
# ============================================================================

def clear_screen():
    """Очистка экрана"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(text: str):
    """Печать заголовка"""
    print("\n" + "=" * 60)
    print(f"📰 {text}")
    print("=" * 60)

def run_test_mode():
    """Режим тестирования"""
    clear_screen()
    print_header("ТЕСТИРОВАНИЕ АГЕНТА")
    
    try:
        print("1. Инициализация агента...")
        agent = NewsAgentV2()
        
        print("\n2. Проверка статуса...")
        stats = agent.get_statistics()
        print(f"   • Модель: {stats['model']}")
        print(f"   • Новостей в базе: {stats['statistics']['total_news']}")
        print(f"   • Проанализировано: {stats['statistics']['analyzed_news']}")
        print(f"   • Анализов выполнено: {stats['statistics']['total_analyses']}")
        
        print("\n3. Тест вызова модели...")
        test_response = agent.call_llm("Привет! Ответь одним предложением.", max_tokens=50)
        print(f"   Ответ модели: {test_response}")
        
        print("\n4. Тест суммаризации...")
        test_text = "Ученые разработали новый алгоритм искусственного интеллекта для медицинской диагностики."
        summary = agent.summarize_text(test_text)
        print(f"   Резюме: {summary}")
        
        print("\n5. Тест извлечения ключевых слов...")
        keywords = agent.extract_keywords(test_text)
        print(f"   Ключевые слова: {', '.join(keywords)}")
        
        input("\n🎯 Нажмите Enter для продолжения...")
        
        print_header("СБОР И АНАЛИЗ НОВОСТЕЙ")
        
        print("\n6. Сбор новостей (тестовый режим)...")
        agent.collect_news(limit_per_source=2)
        
        print("\n7. Анализ собранных новостей...")
        agent.analyze_news_articles(limit=2)
        
        print("\n8. Тестовый анализ темы...")
        result = agent.analyze_topic("искусственный интеллект")
        
        if result["success"]:
            print(f"\n   ✅ Анализ успешен!")
            print(f"   ⏱️  Время: {result['analysis_time_seconds']} сек")
            print(f"   🔑 Ключевые слова: {', '.join(result['keywords'][:5])}")
            
            # Показываем начало анализа
            if result["analysis"]:
                lines = result["analysis"].split('\n')[:10]
                print(f"\n   📊 Начало анализа:")
                for line in lines:
                    if line.strip():
                        print(f"   {line}")
        else:
            print(f"   ❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}")
        
        print_header("ФИНАЛЬНАЯ СТАТИСТИКА")
        final_stats = agent.get_statistics()
        print(f"\n📊 СТАТИСТИКА:")
        print(f"   • Всего новостей: {final_stats['statistics']['total_news']}")
        print(f"   • Проанализировано: {final_stats['statistics']['analyzed_news']}")
        print(f"   • Анализов: {final_stats['statistics']['total_analyses']}")
        print(f"   • Размер базы: {final_stats['database_size_mb']:.2f} MB")
        
        if final_stats['statistics']['categories']:
            print(f"\n📈 РАСПРЕДЕЛЕНИЕ ПО КАТЕГОРИЯМ:")
            for cat, count in final_stats['statistics']['categories'].items():
                print(f"   • {cat}: {count}")
        
        print("\n" + "=" * 60)
        print("✅ ТЕСТИРОВАНИЕ УСПЕШНО ЗАВЕРШЕНО!")
        print("=" * 60)
        
        input("\n🎯 Нажмите Enter для выхода в главное меню...")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Тест прерван пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()
        input("\n🎯 Нажмите Enter для продолжения...")

def run_interactive_mode():
    """Интерактивный режим работы"""
    clear_screen()
    
    try:
        print_header("ИНИЦИАЛИЗАЦИЯ АГЕНТА")
        agent = NewsAgentV2()
        
        while True:
            clear_screen()
            print_header("ГЛАВНОЕ МЕНЮ")
            
            print("\nВыберите действие:")
            print("1. 📰 Собрать новости")
            print("2. 🔍 Проанализировать новости")
            print("3. 🎯 Анализ темы")
            print("4. 🔎 Поиск новостей")
            print("5. 📊 Статистика")
            print("6. 🧪 Тест модели")
            print("7. 🚪 Выход")
            
            choice = input("\nВаш выбор (1-7): ").strip()
            
            if choice == "1":
                clear_screen()
                print_header("СБОР НОВОСТЕЙ")
                limit = input("\nСколько статей с каждого источника? (по умолчанию 3): ").strip()
                limit = int(limit) if limit.isdigit() else 3
                agent.collect_news(limit_per_source=limit)
                input("\n🎯 Нажмите Enter для продолжения...")
                
            elif choice == "2":
                clear_screen()
                print_header("АНАЛИЗ НОВОСТЕЙ")
                limit = input("\nСколько новостей проанализировать? (по умолчанию 5): ").strip()
                limit = int(limit) if limit.isdigit() else 5
                agent.analyze_news_articles(limit=limit)
                input("\n🎯 Нажмите Enter для продолжения...")
                
            elif choice == "3":
                clear_screen()
                print_header("АНАЛИЗ ТЕМЫ")
                topic = input("\nВведите тему для анализа: ").strip()
                if topic:
                    result = agent.analyze_topic(topic)
                    
                    clear_screen()
                    print_header(f"РЕЗУЛЬТАТ АНАЛИЗА: {topic}")
                    
                    if result["success"]:
                        print(f"\n📊 ИНФОРМАЦИЯ:")
                        print(f"   ⏱️  Время анализа: {result['analysis_time_seconds']} сек")
                        print(f"   📰 Использовано новостей: {result['relevant_news_count']}")
                        print(f"   🔑 Ключевые слова: {', '.join(result['keywords'][:8])}")
                        
                        print(f"\n📝 АНАЛИЗ:")
                        print("-" * 60)
                        print(result["analysis"])
                        print("-" * 60)
                    else:
                        print(f"\n❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}")
                    
                    input("\n🎯 Нажмите Enter для продолжения...")
                
            elif choice == "4":
                clear_screen()
                print_header("ПОИСК НОВОСТЕЙ")
                query = input("\nВведите запрос для поиска: ").strip()
                if query:
                    results = agent.search_news(query, limit=10)
                    
                    clear_screen()
                    print_header(f"РЕЗУЛЬТАТЫ ПОИСКА: '{query}'")
                    print(f"\nНайдено: {len(results)} новостей\n")
                    
                    for i, news in enumerate(results, 1):
                        print(f"{i}. {news['title']}")
                        print(f"   📍 Источник: {news['source']}")
                        print(f"   🏷️  Категория: {news['category']}")
                        if news.get('summary'):
                            print(f"   📝 Резюме: {news['summary']}")
                        print()
                    
                    input("\n🎯 Нажмите Enter для продолжения...")
                
            elif choice == "5":
                clear_screen()
                print_header("СТАТИСТИКА")
                stats = agent.get_statistics()
                
                print(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
                print(f"   🤖 Модель: {stats['model']}")
                print(f"   📰 Всего новостей: {stats['statistics']['total_news']}")
                print(f"   🔍 Проанализировано: {stats['statistics']['analyzed_news']}")
                print(f"   📈 Покрытие анализа: {stats['statistics']['analysis_coverage']}")
                print(f"   🎯 Выполнено анализов: {stats['statistics']['total_analyses']}")
                print(f"   💾 Размер базы: {stats['database_size_mb']:.2f} MB")
                
                if stats['statistics']['categories']:
                    print(f"\n📈 РАСПРЕДЕЛЕНИЕ ПО КАТЕГОРИЯМ:")
                    for cat, count in sorted(
                        stats['statistics']['categories'].items(), 
                        key=lambda x: x[1], 
                        reverse=True
                    ):
                        print(f"   • {cat}: {count}")
                
                if stats.get('recent_news'):
                    print(f"\n🕐 ПОСЛЕДНИЕ НОВОСТИ:")
                    for news in stats['recent_news'][:3]:
                        print(f"   • {news['title']}")
                        print(f"     [{news['source']}, {news['published']}]")
                
                input("\n🎯 Нажмите Enter для продолжения...")
                
            elif choice == "6":
                clear_screen()
                print_header("ТЕСТ МОДЕЛИ")
                test_prompt = input("\nВведите тестовый запрос: ").strip()
                if test_prompt:
                    response = agent.call_llm(test_prompt, max_tokens=200)
                    print(f"\n🤖 ОТВЕТ МОДЕЛИ:\n{response}\n")
                    input("🎯 Нажмите Enter для продолжения...")
                
            elif choice == "7":
                print("\n👋 Выход из программы...")
                break
                
            else:
                print("\n❌ Неверный выбор. Попробуйте снова.")
                input("🎯 Нажмите Enter для продолжения...")
                
    except KeyboardInterrupt:
        print("\n\n👋 Выход из программы...")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        input("\n🎯 Нажмите Enter для выхода...")

def main():
    """Главная функция"""
    clear_screen()
    
    print("=" * 70)
    print("🤖 НОВОСТНОЙ ИИ-АГЕНТ v2.0")
    print("=" * 70)
    print("Автономная версия с SQLite базой")
    print("Требуется только: Python 3.8+, Ollama с моделью LLaMA")
    print("=" * 70)
    
    while True:
        print("\nВыберите режим работы:")
        print("1. 🧪 Тестовый режим (рекомендуется для первого запуска)")
        print("2. 💬 Интерактивный режим")
        print("3. 🚪 Выход")
        
        choice = input("\nВаш выбор (1-3): ").strip()
        
        if choice == "1":
            run_test_mode()
        elif choice == "2":
            run_interactive_mode()
        elif choice == "3":
            print("\n👋 До свидания!")
            break
        else:
            print("\n❌ Неверный выбор. Попробуйте снова.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Программа прервана пользователем")
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()