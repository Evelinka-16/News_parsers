import os
import time
import json
import sqlite3
import logging
import importlib
import sys
from datetime import datetime
from collections import defaultdict

import db_functions as db

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("monitor.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)


def load_config(config_path="config.json"):
    if not os.path.exists(config_path):
        logging.error(f"Файл настроек {config_path} не найден!")
        sys.exit(1)
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def create_database(config):
    logging.info("Проверяем таблицы в базе данных и создаём недостающие...")

    con, cur = db.connect(config["news_db"])
    if con:
        db.table_news(con, cur)
        db.table_categories(con, cur)
        db.table_university(con, cur)
        con.close()

    con, cur = db.connect(config["users_db"])
    if con:
        db.table_users(con, cur)
        con.close()


def load_parsers(parsers_dir):
    parsers = []
    if not os.path.exists(parsers_dir):
        logging.error(f"Папка с парсерами {parsers_dir} не найдена!")
        return parsers

    for filename in os.listdir(parsers_dir):
        if filename.startswith("parser_") and filename.endswith(".py"):
            module_name = f"{parsers_dir}.{filename[:-3]}"
            try:
                module = importlib.import_module(module_name)
                if hasattr(module, 'parse'):
                    parsers.append(module)
                    logging.info(f"Парсер подключён: {filename}")
            except Exception as e:
                logging.error(f"Не удалось подключить парсер {filename}: {e}")
    return parsers


def create_send_list(config, last_run):
    try:
        con = sqlite3.connect(config["news_db"])
        cur = con.cursor()
        cur.execute(f"ATTACH DATABASE '{config['users_db']}' AS users_db")

        query = """
            SELECT uc.user_id, n.id
            FROM news n
            JOIN users_db.user_categories uc ON n.category_id = uc.category_id
            WHERE n.added_at > ?
            ORDER BY uc.user_id, n.id
        """
        cur.execute(query, (last_run,))
        rows = cur.fetchall()

        user_news = defaultdict(list)
        for user_id, news_id in rows:
            user_news[user_id].append(str(news_id))

        with open(config["output_file"], "w", encoding="utf-8") as f:
            for uid, nids in user_news.items():
                f.write(f"{uid}: {', '.join(nids)}\n")

        logging.info(f"Рассылка сформирована для {len(user_news)} пользователей")
        con.close()
    except sqlite3.Error as e:
        logging.error(f"Ошибка базы данных при формировании рассылки: {e}")


def main():
    config = load_config()

    create_database(config)

    parsers = load_parsers(config["parsers_dir"])
    if not parsers:
        logging.error("Ни один парсер не подключился, завершаем работу.")
        return

    last_run = "1970-01-01 00:00:00"

    logging.info("Мониторинг запущен. Для остановки нажмите Ctrl+C.")

    try:
        while True:
            cycle_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logging.info("--- Запускаем очередной цикл сбора новостей ---")

            for parser in parsers:
                try:
                    parser.parse()
                except Exception as e:
                    logging.error(f"Парсер {parser.__name__} завершился с ошибкой: {e}")

            create_send_list(config, last_run)
            last_run = cycle_start

            logging.info(f"Цикл завершён. Следующий запуск через {config['interval_minutes']} минут.")
            time.sleep(config["interval_minutes"] * 60)

    except KeyboardInterrupt:
        logging.info("Мониторинг остановлен пользователем")
    except Exception as e:
        logging.critical(f"Непредвиденная ошибка: {e}")


if __name__ == "__main__":
    main()