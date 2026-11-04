"""Применяет db/migrations/V{номер}__{имя}.sql по порядку (docs/stage3/db-design.md, раздел 8).

Запускается одноразовым сервисом migrate от владельца схемы:
    python -m app.migrate
Каждый файл в своей транзакции. Версия 1 — схема этапов I–II из db/01_schema.sql,
она записывается как уже применённая. Если у применённого файла изменилась
контрольная сумма, раннер останавливается: менять применённые миграции нельзя.
"""

import hashlib
import os
import re
import sys
import time
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(os.getenv("MIGRATIONS_DIR", "/app/migrations"))
FILE_RE = re.compile(r"^V(\d+)__(\w+)\.sql$")


def connect(attempts: int = 30) -> psycopg.Connection:
    # При первом запуске тома healthcheck БД может стать зелёным ещё во время
    # init-скриптов (временный сервер слушает только сокет), поэтому ждём TCP
    for attempt in range(1, attempts + 1):
        try:
            return psycopg.connect(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", "5432")),
                dbname=os.environ["DB_NAME"],
                user=os.environ["DB_USER"],
                password=os.environ["DB_PASSWORD"],
                connect_timeout=5,
            )
        except psycopg.OperationalError:
            if attempt == attempts:
                raise
            print("БД ещё не принимает подключения, жду...", flush=True)
            time.sleep(2)


def find_migrations() -> list[tuple[int, str, Path]]:
    found = []
    for path in MIGRATIONS_DIR.glob("*.sql"):
        m = FILE_RE.match(path.name)
        if not m:
            sys.exit(f"Неверное имя файла миграции: {path.name}")
        found.append((int(m.group(1)), m.group(2), path))
    found.sort()
    versions = [v for v, _, _ in found]
    if len(versions) != len(set(versions)):
        sys.exit("Две миграции с одним номером")
    return found


def main() -> None:
    migrations = find_migrations()
    with connect() as conn:
        with conn.transaction():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version    INTEGER      PRIMARY KEY,
                    name       VARCHAR(100) NOT NULL,
                    checksum   CHAR(64)     NOT NULL,
                    applied_at TIMESTAMPTZ  NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                "INSERT INTO schema_migrations (version, name, checksum) "
                "VALUES (1, 'baseline_stage2', repeat('0', 64)) ON CONFLICT (version) DO NOTHING"
            )
            # Приложение может читать версию схемы, но не менять её
            conn.execute("REVOKE INSERT, UPDATE ON schema_migrations FROM kroy_app")
            conn.execute("GRANT SELECT ON schema_migrations TO kroy_app")

        applied = dict(conn.execute("SELECT version, checksum FROM schema_migrations").fetchall())

        for version, name, path in migrations:
            sql = path.read_bytes()
            checksum = hashlib.sha256(sql).hexdigest()
            if version in applied:
                if applied[version] != checksum:
                    sys.exit(f"{path.name}: файл изменён после применения, миграцию менять нельзя")
                continue
            print(f"Применяю {path.name}", flush=True)
            with conn.transaction():
                conn.execute(sql.decode())
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
                    (version, name, checksum),
                )
    print("Миграции применены", flush=True)


if __name__ == "__main__":
    main()
