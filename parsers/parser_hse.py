from datetime import datetime
import time
from urllib.parse import urljoin

import requests as rq
import pandas as pd
from bs4 import BeautifulSoup

import db_functions as db


def timer(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f'Программа заняла: {end - start:.2f} секунд')
        print("=" * 100)
        return result
    return wrapper


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
BASE = 'https://www.hse.ru/news/'
UNIVERSITY_NAME = 'ВШЭ'

PAGES_PER_CATEGORY = 10  # сколько страниц смотрим по каждой категории за один проход

MONTHS = {
    'янв': '01', 'фев': '02', 'мар': '03', 'апр': '04',
    'май': '05', 'мая': '05', 'июн': '06', 'июл': '07', 'авг': '08',
    'сен': '09', 'окт': '10', 'ноя': '11', 'дек': '12'
}

# рубрики сайта ВШЭ -> общие категории из таблицы news_categories (db_functions.py)
# имена здесь должны ТОЧНО совпадать со строками в news_categories,
# иначе get_category_id() не найдёт id и новость уйдёт в "Без категории"
CATEGORIES = {
    'admission/': 'Абитуриентам',
    'edu/': 'Образование',
    'science/': 'Наука и инновации',
    'expertise/': 'Сотрудничество и партнерство',
    'community/': 'Культура и творчество',
    'communication/': 'Международная деятельность',
    'life/': 'Студенческая жизнь',
}

DEFAULT_CATEGORY_ID = 10  # "Без категории" — используем, если имя не нашлось в таблице


def parse_date(item):
    day_tag = item.select_one('div.post-meta__day')
    month_tag = item.select_one('div.post-meta__month')
    year_tag = item.select_one('div.post-meta__year')

    if day_tag is None or month_tag is None or year_tag is None:
        return None

    month_num = MONTHS.get(month_tag.text.strip())
    if month_num is None:
        return None

    return f"{year_tag.text.strip()}-{month_num}-{day_tag.text.strip().zfill(2)}"


@timer
def parse(database="news.db"):
    """Главная функция парсера. Вызывается main.py как parser.parse() —
    без аргументов, поэтому у database есть значение по умолчанию."""

    con, cur = db.connect(database)
    if con is None:
        print("Не удалось подключиться к БД, выходим")
        return

    print("=" * 100)
    print('Собираем новости ВШЭ по категориям')
    print("=" * 100)

    university_id = db.get_university_id(cur, UNIVERSITY_NAME)
    if university_id is None:
        print(f"Университет '{UNIVERSITY_NAME}' не найден в таблице universities")
        con.close()
        return

    data = {
        "title": [], "published_date": [], "link": [],
        "added_at": [], "category_id": [], "university_id": [], "content": []
    }

    for path, category_name in CATEGORIES.items():
        category_id = db.get_category_id(cur, category_name) or DEFAULT_CATEGORY_ID

        for page in range(1, PAGES_PER_CATEGORY + 1):
            url = BASE + path if page == 1 else BASE + path + f'page{page}.html'

            try:
                response = rq.get(url, headers=HEADERS, timeout=10)
            except Exception as e:
                print(f"Ошибка запроса {url}: {e}")
                continue

            if response.status_code != 200:
                print(f"Ошибка {response.status_code} на {url}")
                continue

            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.select('div.post')

            if not items:
                break  # страницы в этой категории кончились

            for item in items:
                h2 = item.find('h2')
                a = h2.find('a') if h2 else None
                if a is None:
                    continue

                date_str = parse_date(item)
                if date_str is None:
                    continue

                data["title"].append(a.get_text(strip=True))
                data["published_date"].append(date_str)
                data["link"].append(urljoin(url, a['href']))
                data["added_at"].append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                data["category_id"].append(category_id)
                data["university_id"].append(university_id)
                data["content"].append("no text")

        print(f'Категория "{category_name}": собрано новостей -', len(data["title"]))

    if not data["title"]:
        print("Новостей не найдено")
        con.close()
        return

    df = pd.DataFrame(data)
    df['published_date'] = pd.to_datetime(df['published_date'], format='%Y-%m-%d')

    before = len(df)
    df = df.drop_duplicates(subset=["link"])
    print(f"Удалено дубликатов внутри выгрузки: {before - len(df)}")

    # не вставляем через db.insert_news() — у неё в общем db_functions.py
    # конфликтующая сигнатура (переопределена другим парсером), поэтому
    # пишем сами через to_sql и сами отфильтровываем то, что уже есть в БД
    existing_links = {row[0] for row in cur.execute("SELECT link FROM news").fetchall()}
    df = df[~df["link"].isin(existing_links)]

    if df.empty:
        print("Новых новостей для ВШЭ нет")
        con.close()
        return

    df.to_sql(name='news', con=con, if_exists='append', index=False)

    print("=" * 100)
    print(f'Парсинг закончен, сохранено новых новостей: {len(df)}')

    con.close()


if __name__ == "__main__":
    parse()