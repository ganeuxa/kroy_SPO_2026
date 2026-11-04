-- Этап III: заказы с резервом остатка, оплата, история статусов, админка.
-- Эталон: docs/stage3/db-changes.sql. Отличие одно: таблицу schema_migrations
-- и записи о версиях ведёт раннер backend/app/migrate.py, транзакцию открывает он же.
-- Применяется владельцем схемы (kroy_owner) поверх 01_schema.sql и 02_seed.sql.

-- Пункты выдачи ---------------------------------------------------------------
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

-- Заказы ----------------------------------------------------------------------
ALTER TABLE orders
    ADD COLUMN pickup_point_id BIGINT REFERENCES pickup_points (id),
    ADD COLUMN comment         VARCHAR(500),
    ADD COLUMN expires_at      TIMESTAMPTZ,
    ADD COLUMN cancel_reason   VARCHAR(16)
               CHECK (cancel_reason IN ('customer', 'expired', 'admin', 'payment_failed')),
    ADD COLUMN checkout_key    UUID,
    ADD COLUMN updated_at      TIMESTAMPTZ NOT NULL DEFAULT now();

UPDATE orders o
SET pickup_point_id = p.id
FROM pickup_points p
WHERE o.delivery_method = 'pickup' AND p.address = o.delivery_address;

ALTER TABLE orders ALTER COLUMN delivery_address DROP NOT NULL;
UPDATE orders SET delivery_address = NULL WHERE delivery_method = 'pickup';
UPDATE orders SET cancel_reason = 'customer' WHERE status = 'cancelled';
-- Старые неоплаченные заказы не истекают (expires_at = NULL): остаток под них не списывался
UPDATE orders SET updated_at = created_at;

ALTER TABLE orders
    ADD CONSTRAINT chk_orders_delivery CHECK (
        (delivery_method = 'courier' AND delivery_address IS NOT NULL AND pickup_point_id IS NULL)
     OR (delivery_method = 'pickup'  AND pickup_point_id  IS NOT NULL AND delivery_address IS NULL)
    ),
    ADD CONSTRAINT chk_orders_cancel CHECK ((status = 'cancelled') = (cancel_reason IS NOT NULL)),
    ADD CONSTRAINT uq_orders_checkout UNIQUE (user_id, checkout_key);

CREATE INDEX idx_orders_expiring ON orders (expires_at) WHERE status = 'new';
CREATE INDEX idx_orders_status_created ON orders (status, created_at DESC);

-- История статусов заказа -----------------------------------------------------
CREATE TABLE order_status_history (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id    BIGINT      NOT NULL REFERENCES orders (id),
    from_status VARCHAR(16),
    to_status   VARCHAR(16) NOT NULL
                CHECK (to_status IN ('new', 'paid', 'shipped', 'delivered', 'cancelled')),
    changed_by  BIGINT      REFERENCES users (id),
    comment     VARCHAR(300),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_status_history_order ON order_status_history (order_id, created_at);

INSERT INTO order_status_history (order_id, from_status, to_status, comment, created_at)
SELECT id, NULL, status, 'Перенесено при миграции V002', created_at
FROM orders;

-- Варианты товара и журнал движения остатков ----------------------------------
ALTER TABLE product_variants
    ADD COLUMN is_active  BOOLEAN     NOT NULL DEFAULT TRUE,
    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE products
    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
UPDATE products SET updated_at = created_at;

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

INSERT INTO stock_movements (variant_id, delta, reason, comment)
SELECT id, stock, 'initial', 'Остаток на момент миграции V002'
FROM product_variants
WHERE stock > 0;

-- Фото товаров в MinIO --------------------------------------------------------
ALTER TABLE product_images
    ADD COLUMN content_type VARCHAR(32)
               CHECK (content_type IN ('image/jpeg', 'image/png', 'image/webp')),
    ADD COLUMN size_bytes   INTEGER CHECK (size_bytes BETWEEN 1 AND 5242880),
    ADD COLUMN created_at   TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE product_images ADD CONSTRAINT uq_images_storage_key UNIQUE (storage_key);

-- Платежи ---------------------------------------------------------------------
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

CREATE UNIQUE INDEX uq_payments_one_succeeded ON payments (order_id) WHERE status = 'succeeded';
CREATE UNIQUE INDEX uq_payments_one_pending   ON payments (order_id) WHERE status = 'pending';

-- Права роли приложения -------------------------------------------------------
-- Новые таблицы получают SELECT, INSERT, UPDATE через ALTER DEFAULT PRIVILEGES (03_app_role.sh).
-- Журналы только дописываются.
REVOKE UPDATE ON order_status_history, stock_movements FROM kroy_app;
