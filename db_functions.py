from datetime import datetime
import sqlite3 as sql

"""Общие функции для работы с БД новостей РЭУ"""

def connect(db="news.db"):
    conn = None
    cursor = None

    try:
        conn = sql.connect(db)
        cursor = conn.cursor()
        return conn, cursor
    except sql.Error as e:
        print(f"[connect] Не удалось подключиться к БД '{db}': {e}")
        if conn:
            conn.close()
        return None, None

def table_news(con, cursor):
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                link TEXT UNIQUE NOT NULL,
                published_date TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                university_id INTEGER NOT NULL,
                added_at TEXT DEFAULT (datetime('now')),
                content TEXT DEFAULT 'no text'
            );
        """)
        con.commit()
    except sql.Error as e:
        print(f"[table_news] Ошибка создания таблицы news: {e}")
        con.rollback()


def table_categories(con, cursor):
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news_categories (
                category_id INTEGER NOT NULL,
                name TEXT NOT NULL
            );
        """)

        count = cursor.execute(
            "SELECT COUNT(*) FROM news_categories;"
        ).fetchone()[0]

        if count == 0:
            print("Справочник категорий пуст — заполняем базовым набором")
            cursor.execute("""
                INSERT INTO news_categories(category_id, name)
                VALUES
                    (1, "Наука и инновации"),
                    (2, "Спорт"),
                    (3, "Абитуриентам"),
                    (4, "Объявления и события"),
                    (5, "Студенческая жизнь"),
                    (6, "Международная деятельность"),
                    (7, "Сотрудничество и партнерство"),
                    (8, "Культура и творчество"),
                    (9, "Образование"),
                    (10, "Без категории");
            """)

        con.commit()
    except sql.Error as e:
        print(f"[table_categories] Ошибка создания таблицы news_categories: {e}")
        con.rollback()


def table_university(con, cursor):
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS universities (
                university_id INTEGER NOT NULL,
                name TEXT NOT NULL
            );
        """)

        count = cursor.execute(
            "SELECT COUNT(*) FROM universities;"
        ).fetchone()[0]

        if count == 0:
            print("Справочник вузов пуст — заполняем базовым набором")
            cursor.execute("""
                INSERT INTO universities(university_id, name)
                VALUES
                    (1, "РЭУ"),
                    (2, "МИРЭА"),
                    (3, "ВШЭ"),
                    (4, "МИСИС"),
                    (5, "МФТИ"),
                    (6, "МАИ"),
                    (7, "КФУ"),
                    (8, "МГУ"),
                    (9, "unknown");
            """)

        con.commit()
    except sql.Error as e:
        print(f"[table_university] Ошибка создания таблицы universities: {e}")
        con.rollback()


def table_users(con, cursor):
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_categories (
                user_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)

        count = cursor.execute("SELECT COUNT(*) FROM users;").fetchone()[0]

        if count == 0:
            print("Таблица пользователей пуста — добавляем тестовых подписчиков")

            cursor.execute("""
                INSERT INTO users (id, name, email) VALUES
                (1, 'Герман', 'german@example.com'),
                (2, 'Ваня', 'ivan@example.com'),
                (3, 'Макс', 'maxim@example.com'),
                (4, 'Эвелина', 'evelina@example.com'),
                (5, 'Вика', 'vika@example.com');
            """)

            cursor.execute("""
                INSERT INTO user_categories (user_id, category_id) VALUES
                (1, 1), (1, 9), (1, 5),
                (2, 2), (2, 8),
                (3, 3), (3, 4), (3, 9),
                (4, 1), (4, 6), (4, 7), (4, 9),
                (5, 5), (5, 2);
            """)

        con.commit()
    except sql.Error as e:
        print(f"[table_users] Ошибка создания таблиц пользователей: {e}")
        con.rollback()


def insert_news(
    con,
    cursor,
    title,
    date,
    link,
    category: int,
    university: int,
    content: str,
):
    try:
        # title/date могут прийти и обычной строкой, и тегом bs4 — поддерживаем оба варианта
        title_str = (
            title.text.strip() if hasattr(title, "text") else str(title).strip()
        )
        date_str = (
            date.text.strip() if hasattr(date, "text") else str(date).strip()
        )

        cursor.execute(
            """
            INSERT OR IGNORE INTO news(
                title, published_date, link, added_at,
                category_id, university_id, content
            )
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title_str,
                date_str,
                link,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                category,
                university,
                content,
            ),
        )

        if cursor.rowcount == 1:
            print(f"Новая запись добавлена: {title_str}")
        else:
            print("Такая новость уже есть в базе, пропускаем")

        con.commit()
    except sql.Error as e:
        print(f"[insert_news] Ошибка вставки записи: {e}")
        con.rollback()


def view_data(cursor):
    try:
        data = cursor.execute("SELECT * FROM news").fetchall()
        row_count = cursor.execute("SELECT COUNT(*) FROM news").fetchone()[0]
        return data, row_count
    except sql.Error as e:
        print(f"[view_data] Ошибка чтения таблицы news: {e}")
        return [], 0


def truncate_table(con, cursor):
    try:
        cursor.execute("DELETE FROM news")
        con.commit()
        print("Таблица news очищена")
    except sql.Error as e:
        print(f"[truncate_table] Ошибка очистки таблицы news: {e}")
        con.rollback()


def get_last_news(cursor, uni: str="РЭУ"):
    try:
        uni = uni.upper()

        cursor.execute(
            """
            SELECT title
            FROM news n
            JOIN universities u ON n.university_id = u.university_id
            WHERE u.name = ?
            ORDER BY published_date DESC, id ASC
            LIMIT 1
            """,
            (uni,),
        )

        result = cursor.fetchone()
        return result if result else f"Записей для вуза «{uni}» пока нет"
    except sql.Error as e:
        print(f"[get_last_news] Ошибка выборки последней новости: {e}")
        return None


def truncate(con, cursor, table_name: str):

    try:
        cursor.execute(f"DELETE FROM {table_name}")
        con.commit()
        print(f"Таблица {table_name} очищена")
    except sql.Error as e:
        print(f"[truncate] Ошибка очистки таблицы {table_name}: {e}")
        con.rollback()


def clear_database(con, cursor):
    user_input = input(
        "Внимание: эта операция полностью очищает базу данных.\n"
        "Чтобы подтвердить, введите 'yes': "
    )

    if user_input.strip().lower() == "yes":
        try:
            cursor.execute("DELETE FROM news")
            cursor.execute("DELETE FROM news_categories")
            cursor.execute("DELETE FROM universities")
            cursor.execute(
                "UPDATE sqlite_sequence SET seq = 0 WHERE name = 'news'"
            )
            con.commit()
            print("База данных полностью очищена")
        except sql.Error as e:
            print(f"[clear_database] Ошибка при очистке базы: {e}")
            con.rollback()
    else:
        print("Очистка отменена пользователем")

"""Общие функции для работы с БД новостей МИРЭА"""

import sqlite3


def connect_get_cursor(db):
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        return conn, cursor
    except sqlite3.Error as e:
        print(f"[connect_get_cursor] Не удалось подключиться к БД: {e}")
        if conn:
            conn.close()
        return None, None


def create_news_table(cursor, conn):
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news(
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                link TEXT UNIQUE NOT NULL,
                published_date TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                university_id INTEGER NOT NULL,
                content TEXT,
                added_at TEXT DEFAULT (datetime('now'))
            );
        ''')
        conn.commit()
    except sqlite3.Error as e:
        print(f"[create_news_table] Ошибка создания таблицы news: {e}")
        conn.rollback()


def create_categories_table(cursor, conn):
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news_categories (
                category_id INTEGER NOT NULL,
                name TEXT NOT NULL
            );
        ''')

        num = cursor.execute('''
            SELECT COUNT(*) FROM news_categories;
        ''').fetchone()

        if num[0] == 0:
            cursor.execute('''
                INSERT INTO news_categories (category_id, name) VALUES
                (1, 'Наука и инновации'),
                (2, 'Спорт'),
                (3, 'Абитуриентам'),
                (4, 'Объявления и события'),
                (5, 'Студенческая жизнь'),
                (6, 'Международная деятельность'),
                (7, 'Сотрудничество и партнерство'),
                (8, 'Культура и творчество'),
                (9, 'Образование'),
                (10, 'Без категории')
            ''')
        conn.commit()
    except sqlite3.Error as e:
        print(f"[create_categories_table] Ошибка создания справочника категорий: {e}")
        conn.rollback()


def create_university_tables(cursor, conn):
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS universities (
                university_id INTEGER NOT NULL,
                name TEXT NOT NULL
            );
        ''')

        num = cursor.execute('''
            SELECT COUNT(*) FROM universities;
        ''').fetchone()
        if num[0] == 0:
            cursor.execute('''
                INSERT INTO universities (university_id, name) VALUES
                (1, 'РЭУ'),
                (2, 'МИРЭА'),
                (3, 'ВШЭ'),
                (4, 'МИСИС'),
                (5, 'МФТИ'),
                (6, 'МАИ'),
                (7, 'КФУ'),
                (8, 'МГУ'),
                (9, 'unknown')
            ''')
        conn.commit()
    except sqlite3.Error as e:
        print(f"[create_university_tables] Ошибка создания справочника вузов: {e}")
        conn.rollback()


def get_university_id(cursor, name):
    try:
        uni_id = cursor.execute('''
            SELECT university_id FROM universities
            WHERE name = ?;
        ''', (name,)).fetchone()
        return uni_id[0] if uni_id else None
    except sqlite3.Error as e:
        print(f"[get_university_id] Ошибка поиска id вуза: {e}")
        return None
    finally:
        pass


def get_category_id(cursor, cat):
    try:
        cat_id = cursor.execute('''
            SELECT category_id FROM news_categories
            WHERE name = ?;
        ''', (cat,)).fetchone()
        return cat_id[0] if cat_id else None
    except sqlite3.Error as e:
        print(f"[get_category_id] Ошибка поиска id категории: {e}")
        return None


def get_last_link(cursor):
    try:
        row = cursor.execute('''
            SELECT link FROM news n
            JOIN universities u ON u.university_id = n.university_id
            WHERE u.name = 'МИРЭА'
            ORDER BY published_date DESC
            LIMIT 1;
        ''').fetchone()

        link = row[0] if row else None
        return link
    except sqlite3.Error as e:
        print(f"[get_last_link] Ошибка поиска последней ссылки: {e}")
        return None


def print_all_rows(cursor):
    try:
        cursor.execute('''
            SELECT *
            FROM news
        ''')
        print(cursor.fetchall())
    except sqlite3.Error as e:
        print(f"[print_all_rows] Ошибка чтения таблицы: {e}")


def insert_news(cursor, conn, title, link, dt, category_id, university_id, content):
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO news (title, link, published_date, category_id, university_id, content) VALUES (?, ?, ?, ?, ?, ?);
        ''', (title, link, dt, category_id, university_id, content))
        conn.commit()
    except sqlite3.Error as e:
        print(f"[insert_news] Ошибка вставки записи: {e}")
        conn.rollback()


def create_users_table(cursor, conn):
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT
            );
        ''')

        num = cursor.execute('''
                SELECT COUNT(*) FROM users;
            ''').fetchone()

        if num[0] == 0:
            cursor.execute('''
                INSERT INTO users (id, name) VALUES
                (1, 'John'),
                (2, 'Mark'),
                (3, 'Ivanka'),
                (4, 'Maynard'),
                (5, 'Mathew')
            ''')
            conn.commit()
    except sqlite3.Error as e:
        print(f"[create_users_table] Ошибка создания таблицы пользователей: {e}")
        conn.rollback()


def create_user_cat_table(cursor, conn):
    try:
        cursor.execute('''
               CREATE TABLE IF NOT EXISTS user_categories (
                   user_id INTEGER NOT NULL,
                   category_id INTEGER NOT NULL,
                   FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
               );
           ''')

        num = cursor.execute('''
                   SELECT COUNT(*) FROM user_categories;
               ''').fetchone()

        if num[0] == 0:
            cursor.execute('''
                   INSERT INTO user_categories (user_id, category_id) VALUES
                   (1, 1),
                   (1, 2),
                   (2, 3),
                   (2, 4),
                   (3, 5),
                   (3, 6),
                   (4, 7),
                   (4, 8),
                   (5, 9),
                   (5, 1)
               ''')
            conn.commit()
    except sqlite3.Error as e:
        print(f"[create_user_cat_table] Ошибка заполнения таблицы подписок: {e}")
        conn.rollback()

if __name__ == "__main__":
    con, cursor = connect()

    print(get_last_news(cursor))