from datetime import datetime
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pandas as pd
import requests as rq

import db_functions as db


def timer(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"Программа заняла: {end - start:.2f} секунд; {(end - start) / 60:.2f} минут")
        print("=" * 100)
        return result

    return wrapper


categories = {
    "Наука": "Наука и инновации",
    "Спорт": "Спорт",
    "Абитуриентам": "Абитуриентам",
    "В мире": "Объявления и события",
    "Образование": "Образование",
    "Студенчество": "Студенческая жизнь",
    "Международная деятельность": "Международная деятельность",
    "Проекты": "Сотрудничество и партнерство",
    "Университет": "Культура и творчество",
}

urls = []
for i in range(1, 5):
    page = f"https://www.rea.ru/news?tree-content-path=news&page={i}&per-page=12"
    urls.append(page)


@timer
def parse(database="news.db", stop_title=None):
    con, cur = db.connect(database)

    result = db.get_last_news(cur, "РЭУ")
    stop_title = result[0] if isinstance(result, tuple) else None

    print("Начинаем парсинг новостей РЭУ")
    print("=" * 100)

    data = {
        "title": [],
        "published_date": [],
        "link": [],
        "added_at": [],
        "category_id": [],
        "university_id": [],
        "content": [],
    }

    stop_parsing = False

    # Добавили заголовки, чтобы сайт думал, что мы обычный браузер
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    for url in urls:
        if stop_parsing:
            break

        try:
            response = rq.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                print(f"Ошибка загрузки страницы {url}: статус {response.status_code}")
                continue
        except (rq.RequestException, TimeoutError) as e:
            print(f"Ошибка сети на странице {url}: {e}")
            continue

        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("a.catalog__item-content")

        for item in items:
            title = item.select_one(".catalog__item-title")
            if not title:
                continue

            title_text = title.get_text(strip=True)
            if title_text == stop_title:
                stop_parsing = True
                break

            date = item.select_one(".catalog__item-date")
            link = urljoin("https://www.rea.ru", item.get("href", ""))
            link = link.split("?")[0]

            try:
                response_sub = rq.get(link, headers=headers, timeout=15)
                if response_sub.status_code != 200:
                    continue
                html_sub = response_sub.text
                soup_sub = BeautifulSoup(html_sub, "html.parser")
            except (rq.RequestException, TimeoutError) as e:
                print(f"Ошибка загрузки {link}: {e}, пропускаем новость...")
                continue

            category_tag = soup_sub.select_one("li.catalog-detail__tag")
            content_tag = soup_sub.select_one(".catalog-detail__text")

            short_content = (
                content_tag.get_text(" ", strip=True) if content_tag else "no text"
            )

            if category_tag:
                cat_raw = category_tag.get_text(strip=True)
                category_name = categories.get(cat_raw, "Без категории")
            else:
                category_name = "Без категории"

            cat_row = cur.execute(
                "SELECT category_id FROM news_categories WHERE name = ?",
                (category_name,),
            ).fetchone()
            cat_id = cat_row[0] if cat_row else 10

            date_text = date.get_text(strip=True) if date else ""
            if date_text == "Сегодня":
                date_text = datetime.now().strftime("%d %m %Y")

            uni_row = cur.execute(
                "SELECT university_id FROM universities WHERE name = ?", ("РЭУ",)
            ).fetchone()
            uni_id = uni_row[0] if uni_row else 1

            data["title"].append(title_text)
            data["published_date"].append(date_text)
            data["link"].append(link)
            data["added_at"].append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            data["category_id"].append(cat_id)
            data["university_id"].append(uni_id)
            data["content"].append(short_content)

            print("Новость РЭУ добавлена")

    if not data["title"]:
        print("Новых новостей для РЭУ пока нет.")
        return

    df = pd.DataFrame(data)

    months = {
        "января": "01",
        "февраля": "02",
        "марта": "03",
        "апреля": "04",
        "мая": "05",
        "июня": "06",
        "июля": "07",
        "августа": "08",
        "сентября": "09",
        "октября": "10",
        "ноября": "11",
        "декабря": "12",
    }

    df["published_date"] = df["published_date"].replace(months, regex=True)
    df["published_date"] = pd.to_datetime(
        df["published_date"], format="%d %m %Y", errors="coerce"
    )
    df["category_id"] = df["category_id"].astype("int")

    before = len(df)
    df = df.drop_duplicates(subset=["link"])
    after = len(df)
    print(f"Удалено дубликатов: {before - after}")

    existing_links = {
        row[0] for row in cur.execute("SELECT link FROM news").fetchall()
    }
    df = df[~df["link"].isin(existing_links)]

    if df.empty:
        print("Новых уникальных новостей для записи нет.")
        return

    print(f"🔥 Обнаружено новых новостей: {len(df)}")
    df.to_sql(name="news", con=con, if_exists="append", index=False)

    print("=" * 100)
    print(f"Парсинг закончился, в базу данных сохранено {len(df)} новостей!")


if __name__ == "__main__":
    parse()