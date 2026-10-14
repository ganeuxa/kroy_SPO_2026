#!/bin/sh
# Создаёт роль приложения kroy_app с ограниченными правами (см. отчёт №4, п.3).
# Пароль берётся из переменной KROY_APP_PASSWORD, в репозиторий он не попадает.
# Скрипт выполняется один раз, при первом создании тома с данными.
set -e

if [ -z "$KROY_APP_PASSWORD" ]; then
    echo "KROY_APP_PASSWORD не задан" >&2
    exit 1
fi

psql -v ON_ERROR_STOP=1 \
     --username "$POSTGRES_USER" \
     --dbname "$POSTGRES_DB" \
     -v app_password="$KROY_APP_PASSWORD" \
     -v owner="$POSTGRES_USER" <<'EOSQL'
CREATE ROLE kroy_app LOGIN PASSWORD :'app_password';

GRANT CONNECT ON DATABASE :"DBNAME" TO kroy_app;
GRANT USAGE ON SCHEMA public TO kroy_app;

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO kroy_app;
GRANT DELETE ON cart_items, favorites, reviews, product_images, product_variants TO kroy_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO kroy_app;

-- Таблицы, которые владелец создаст позже (миграциями), получат те же права.
-- DELETE на новые таблицы выдаётся вручную, когда это нужно.
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE ON TABLES TO kroy_app;
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO kroy_app;
EOSQL
