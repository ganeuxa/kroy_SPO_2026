-- Крой, этап III: целевые изменения схемы БД (проект архитектора).
-- Это эталон для миграции db/migrations/V002__stage3.sql: применяется к БД этапа II
-- поверх 01_schema.sql и 02_seed.sql и не теряет существующие данные.
-- Выполняется владельцем схемы (kroy_owner) в одной транзакции.
-- Обоснования: docs/stage3/db-design.md.

BEGIN;

-- 1. Учёт миграций -----------------------------------------------------------
-- Версия 1 — схема этапов I–II (01_schema.sql). Для уже существующих БД она
-- записывается как применённая, потом применяются только новые файлы.
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER     PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    checksum   CHAR(64)    NOT NULL,          -- sha256 файла миграции
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO schema_migrations (version, name, checksum)
VALUES (1, 'baseline_stage2', repeat('0', 64))
ON CONFLICT (version) DO NOTHING;

-- 2. Пункты выдачи (самовывоз) ------------------------------------------------
-- Открытый вопрос №6 этапа I. Раньше при самовывозе в delivery_address писали
-- текст пункта выдачи, а поле было обязательным для любого способа доставки.
CREATE TABLE pickup_points (
    id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name      VARCHAR(120) NOT NULL,
    address   VARCHAR(300) NOT NULL UNIQUE,
    hours     VARCHAR(120),
    is_active BOOLEAN      NOT NULL DEFAULT TRUE
);

-- Пункты из уже оформленных заказов с самовывозом, чтобы не потерять данные
INSERT INTO pickup_points (name, address)
SELECT DISTINCT 'Пункт выдачи', delivery_address
FROM orders
WHERE delivery_method = 'pickup';

-- 3. Заказы -------------------------------------------------------------------
ALTER TABLE orders
    ADD COLUMN pickup_point_id BIGINT REFERENCES pickup_points (id),
    ADD COLUMN comment         VARCHAR(500),
    ADD COLUMN expires_at      TIMESTAMPTZ,      -- до какого момента ждём оплату (только status = 'new')
    ADD COLUMN cancel_reason   VARCHAR(16)
               CHECK (cancel_reason IN ('customer', 'expired', 'admin', 'payment_failed')),
    ADD COLUMN checkout_key    UUID,             -- Idempotency-Key запроса оформления
    ADD COLUMN updated_at      TIMESTAMPTZ NOT NULL DEFAULT now();

UPDATE orders o
SET pickup_point_id = p.id
FROM pickup_points p
WHERE o.delivery_method = 'pickup' AND p.address = o.delivery_address;

ALTER TABLE orders ALTER COLUMN delivery_address DROP NOT NULL;
UPDATE orders SET delivery_address = NULL WHERE delivery_method = 'pickup';
UPDATE orders SET cancel_reason = 'customer' WHERE status = 'cancelled';
-- Старые неоплаченные заказы не истекают автоматически (expires_at остаётся NULL):
-- остаток под них не списывался, возвращать нечего
UPDATE orders SET updated_at = created_at;

ALTER TABLE orders
    ADD CONSTRAINT chk_orders_delivery CHECK (
        (delivery_method = 'courier' AND delivery_address IS NOT NULL AND pickup_point_id IS NULL)
     OR (delivery_method = 'pickup'  AND pickup_point_id  IS NOT NULL AND delivery_address IS NULL)
    ),
    ADD CONSTRAINT chk_orders_cancel CHECK ((status = 'cancelled') = (cancel_reason IS NOT NULL)),
    ADD CONSTRAINT uq_orders_checkout UNIQUE (user_id, checkout_key);

-- Поиск просроченных неоплаченных заказов фоновой задачей
CREATE INDEX idx_orders_expiring ON orders (expires_at) WHERE status = 'new';
-- Список заказов в админке с фильтром по статусу (FR-15)
CREATE INDEX idx_orders_status_created ON orders (status, created_at DESC);

-- 4. История статусов заказа (FR-10, FR-15) ----------------------------------
CREATE TABLE order_status_history (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id    BIGINT      NOT NULL REFERENCES orders (id),
    from_status VARCHAR(16),                    -- NULL для создания заказа
    to_status   VARCHAR(16) NOT NULL
                CHECK (to_status IN ('new', 'paid', 'shipped', 'delivered', 'cancelled')),
    changed_by  BIGINT      REFERENCES users (id), -- NULL: система (оплата, истечение срока)
    comment     VARCHAR(300),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_status_history_order ON order_status_history (order_id, created_at);

-- Для существующих заказов восстанавливаем запись о текущем статусе
INSERT INTO order_status_history (order_id, from_status, to_status, comment, created_at)
SELECT id, NULL, status, 'Перенесено при миграции V002', created_at
FROM orders;

-- 5. Варианты товара и журнал движения остатков (вопрос №1, FR-14, NFR-08) ----
ALTER TABLE product_variants
    ADD COLUMN is_active  BOOLEAN     NOT NULL DEFAULT TRUE,  -- скрыть вариант, не удаляя (на него ссылаются заказы)
    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE products
    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
UPDATE products SET updated_at = created_at;

-- Каждое изменение остатка: резерв при заказе, возврат при отмене, правка админом.
-- По этому журналу при отмене возвращается ровно то, что было списано под заказ.
CREATE TABLE stock_movements (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    variant_id BIGINT      NOT NULL REFERENCES product_variants (id),
    delta      INTEGER     NOT NULL CHECK (delta <> 0),
    reason     VARCHAR(16) NOT NULL
               CHECK (reason IN ('reserve', 'release', 'adjust', 'initial')),
    order_id   BIGINT      REFERENCES orders (id),
    changed_by BIGINT      REFERENCES users (id),
    comment    VARCHAR(300),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((reason IN ('reserve', 'release')) = (order_id IS NOT NULL)),
    CHECK (reason <> 'reserve' OR delta < 0),
    CHECK (reason <> 'release' OR delta > 0)
);
CREATE INDEX idx_stock_movements_variant ON stock_movements (variant_id, created_at DESC);
CREATE INDEX idx_stock_movements_order   ON stock_movements (order_id) WHERE order_id IS NOT NULL;

-- Начальные остатки как первая запись журнала: сумма журнала = текущему stock
INSERT INTO stock_movements (variant_id, delta, reason, comment)
SELECT id, stock, 'initial', 'Остаток на момент миграции V002'
FROM product_variants
WHERE stock > 0;

-- 6. Фото товаров в MinIO (вопрос №3, FR-13) ---------------------------------
ALTER TABLE product_images
    ADD COLUMN content_type VARCHAR(32)
               CHECK (content_type IN ('image/jpeg', 'image/png', 'image/webp')),
    ADD COLUMN size_bytes   INTEGER CHECK (size_bytes BETWEEN 1 AND 5242880),
    ADD COLUMN created_at   TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE product_images ADD CONSTRAINT uq_images_storage_key UNIQUE (storage_key);

-- 7. Платежи (вопрос №7, FR-09, NFR-09) --------------------------------------
ALTER TABLE payments
    ADD COLUMN idempotency_key UUID,
    ADD COLUMN provider        VARCHAR(16) NOT NULL DEFAULT 'test'
               CHECK (provider IN ('test')),
    ADD COLUMN failure_reason  VARCHAR(120);
ALTER TABLE payments
    DROP CONSTRAINT payments_status_check,
    ADD CONSTRAINT payments_status_check
        CHECK (status IN ('pending', 'succeeded', 'failed', 'cancelled')),
    ADD CONSTRAINT uq_payments_idempotency UNIQUE (order_id, idempotency_key);

-- Не больше одного успешного и одного ожидающего платежа на заказ
CREATE UNIQUE INDEX uq_payments_one_succeeded ON payments (order_id) WHERE status = 'succeeded';
CREATE UNIQUE INDEX uq_payments_one_pending   ON payments (order_id) WHERE status = 'pending';

-- 8. Права роли приложения ----------------------------------------------------
-- Новые таблицы получают SELECT, INSERT, UPDATE через ALTER DEFAULT PRIVILEGES (03_app_role.sh).
-- Журналы только дописываются: забираем UPDATE у истории статусов и движения остатков.
REVOKE UPDATE ON order_status_history, stock_movements FROM kroy_app;
GRANT SELECT ON schema_migrations TO kroy_app;
REVOKE INSERT, UPDATE ON schema_migrations FROM kroy_app;

INSERT INTO schema_migrations (version, name, checksum)
VALUES (2, 'stage3_orders_payments_admin', repeat('0', 64));

COMMIT;
