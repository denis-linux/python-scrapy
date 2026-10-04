# Dependency Analyzer (ДЗ3)

Утилита для анализа графа зависимостей Python-проектов.

## Подготовка репозитория

1. Клонируйте репозиторий scrapy:
   git clone https://github.com/scrapy/scrapy.git
2. Переключитесь на нужный коммит:
   git checkout ebfb049

## Запуск

python dependency_analyzer.py <команда> <путь_к_проекту> [файл]

Примеры:

1. Статистика проекта:
python dependency_analyzer.py stats scrapy

2. Анализ влияния (какие файлы сломаются при изменении Request):
python dependency_analyzer.py impact scrapy scrapy/http/request/__init__.py

3. Поиск циклов:
python dependency_analyzer.py cycles scrapy

4. Порядок сборки:
python dependency_analyzer.py order scrapy
