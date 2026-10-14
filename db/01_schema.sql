-- Крой: физическая схема БД (PostgreSQL 16)
-- Порядок создания учитывает внешние ключи.
-- Роль приложения kroy_app и её права создаются в 03_app_role.sh,
-- потому что пароль роли берётся из переменной окружения.

CREATE TABLE users (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(120) NOT NULL,
    phone         VARCHAR(20),
    role          VARCHAR(16)  NOT NULL DEFAULT 'customer'
                  CHECK (role IN ('customer', 'admin')),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE categories (
    id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    slug VARCHAR(80) NOT NULL UNIQUE
);

CREATE TABLE products (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category_id BIGINT         NOT NULL REFERENCES categories (id),
    name        VARCHAR(160)   NOT NULL,
    description TEXT,
    gender      VARCHAR(10)    NOT NULL
                CHECK (gender IN ('men', 'women', 'unisex')),
    price       NUMERIC(10, 2) NOT NULL CHECK (price > 0),
    is_active   BOOLEAN        NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT now()
);

CREATE TABLE product_variants (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id BIGINT      NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    size       VARCHAR(10) NOT NULL,
    color      VARCHAR(40) NOT NULL,
    sku        VARCHAR(40) NOT NULL UNIQUE,
    stock      INTEGER     NOT NULL DEFAULT 0 CHECK (stock >= 0),
    UNIQUE (product_id, size, color)
);

CREATE TABLE product_images (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id  BIGINT       NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    storage_key VARCHAR(255) NOT NULL,
    color       VARCHAR(40),
    sort_order  SMALLINT     NOT NULL DEFAULT 0
);

CREATE TABLE cart_items (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    variant_id BIGINT      NOT NULL REFERENCES product_variants (id) ON DELETE CASCADE,
    quantity   INTEGER     NOT NULL CHECK (quantity > 0),
    added_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, variant_id)
);

CREATE TABLE orders (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id          BIGINT         NOT NULL REFERENCES users (id),
    status           VARCHAR(16)    NOT NULL DEFAULT 'new'
                     CHECK (status IN ('new', 'paid', 'shipped', 'delivered', 'cancelled')),
    total_amount     NUMERIC(10, 2) NOT NULL CHECK (total_amount >= 0),
    delivery_method  VARCHAR(16)    NOT NULL
                     CHECK (delivery_method IN ('courier', 'pickup')),
    delivery_address VARCHAR(300)   NOT NULL,
    contact_phone    VARCHAR(20)    NOT NULL,
    created_at       TIMESTAMPTZ    NOT NULL DEFAULT now()
);

CREATE TABLE order_items (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id          BIGINT         NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    variant_id        BIGINT         NOT NULL REFERENCES product_variants (id),
    quantity          INTEGER        NOT NULL CHECK (quantity > 0),
    price_at_purchase NUMERIC(10, 2) NOT NULL CHECK (price_at_purchase >= 0),
    UNIQUE (order_id, variant_id)
);

CREATE TABLE payments (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id            BIGINT         NOT NULL REFERENCES orders (id),
    provider_payment_id VARCHAR(64) UNIQUE,
    amount              NUMERIC(10, 2) NOT NULL CHECK (amount > 0),
    status              VARCHAR(16)    NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'succeeded', 'cancelled')),
    created_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),
    paid_at             TIMESTAMPTZ,
    CONSTRAINT chk_paid_at CHECK (status <> 'succeeded' OR paid_at IS NOT NULL)
);

CREATE TABLE favorites (
    user_id    BIGINT      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    product_id BIGINT      NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    added_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, product_id)
);

CREATE TABLE reviews (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    product_id BIGINT      NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    rating     SMALLINT    NOT NULL CHECK (rating BETWEEN 1 AND 5),
    body       TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, product_id)
);

-- Индексы под типовые запросы
CREATE INDEX idx_products_category      ON products (category_id);
CREATE INDEX idx_products_gender_active ON products (gender) WHERE is_active;
CREATE INDEX idx_variants_size_color    ON product_variants (size, color);
CREATE INDEX idx_images_product         ON product_images (product_id, sort_order);
CREATE INDEX idx_orders_user_created    ON orders (user_id, created_at DESC);
CREATE INDEX idx_order_items_order      ON order_items (order_id);
CREATE INDEX idx_payments_order         ON payments (order_id);
CREATE INDEX idx_reviews_product        ON reviews (product_id);
