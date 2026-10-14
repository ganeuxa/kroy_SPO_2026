-- Крой: тестовые данные.
-- Хэши паролей настоящие (bcrypt, cost 12), под этими пользователями можно войти.
-- Тестовые пароли: admin@kroy.test -> KroyAdmin-2026, остальные -> KroyTest-2026.
-- Это учебные данные, на реальном стенде пароли нужно сменить.

INSERT INTO users (email, password_hash, full_name, phone, role) VALUES
    ('admin@kroy.test',  '$2b$12$qyIh4/uxMWP1USFfBGlC6uu3mlEG53fcB0sWD5EzKM7d7jymHxLnm', 'Админ Тестовый', NULL,          'admin'),
    ('anna@example.com', '$2b$12$ky.Ncu/ghWoqVOVzztN2ouhU0KLTsaz55bzoRbqffVAN8P8Ot5D/C', 'Анна Смирнова',  '+79001112233', 'customer'),
    ('max@example.com',  '$2b$12$ky.Ncu/ghWoqVOVzztN2ouhU0KLTsaz55bzoRbqffVAN8P8Ot5D/C', 'Максим Орлов',   '+79002223344', 'customer'),
    ('ilya@example.com', '$2b$12$ky.Ncu/ghWoqVOVzztN2ouhU0KLTsaz55bzoRbqffVAN8P8Ot5D/C', 'Илья Фомин',     '+79003334455', 'customer');

INSERT INTO categories (name, slug) VALUES
    ('Футболки',          'tshirts'),
    ('Худи и свитшоты',   'hoodies'),
    ('Джинсы',            'jeans'),
    ('Куртки',            'jackets');

INSERT INTO products (category_id, name, description, gender, price) VALUES
    ((SELECT id FROM categories WHERE slug = 'tshirts'), 'Футболка базовая',        'Плотный хлопок, прямой крой',        'men',    1290.00),
    ((SELECT id FROM categories WHERE slug = 'tshirts'), 'Футболка оверсайз',       'Свободный крой, спущенное плечо',    'women',  1590.00),
    ((SELECT id FROM categories WHERE slug = 'hoodies'), 'Худи с капюшоном',        'Футер с начёсом, карман-кенгуру',    'unisex', 3490.00),
    ((SELECT id FROM categories WHERE slug = 'jeans'),   'Джинсы прямого кроя',     'Классическая посадка',               'men',    4290.00),
    ((SELECT id FROM categories WHERE slug = 'jeans'),   'Джинсы mom fit',          'Высокая посадка, зауженные к низу',  'women',  4590.00),
    ((SELECT id FROM categories WHERE slug = 'jackets'), 'Куртка-бомбер',           'Лёгкая, на молнии, с манжетами',     'men',    6990.00),
    ((SELECT id FROM categories WHERE slug = 'jackets'), 'Куртка стёганая',         'Демисезонная, с воротником-стойкой', 'women',  7490.00),
    ((SELECT id FROM categories WHERE slug = 'hoodies'), 'Свитшот',                 'Без капюшона, мягкий начёс',         'women',  2990.00);

INSERT INTO product_variants (product_id, size, color, sku, stock) VALUES
    ((SELECT id FROM products WHERE name = 'Футболка базовая'),    'M',  'белый',   'TSH-B-M-WHT',  10),
    ((SELECT id FROM products WHERE name = 'Футболка базовая'),    'L',  'белый',   'TSH-B-L-WHT',   8),
    ((SELECT id FROM products WHERE name = 'Футболка базовая'),    'M',  'чёрный',  'TSH-B-M-BLK',  12),
    ((SELECT id FROM products WHERE name = 'Футболка базовая'),    'L',  'чёрный',  'TSH-B-L-BLK',   0),
    ((SELECT id FROM products WHERE name = 'Футболка оверсайз'),   'S',  'чёрный',  'TSH-O-S-BLK',   5),
    ((SELECT id FROM products WHERE name = 'Футболка оверсайз'),   'M',  'чёрный',  'TSH-O-M-BLK',   7),
    ((SELECT id FROM products WHERE name = 'Футболка оверсайз'),   'M',  'серый',   'TSH-O-M-GRY',   4),
    ((SELECT id FROM products WHERE name = 'Худи с капюшоном'),    'M',  'серый',   'HOD-M-GRY',     6),
    ((SELECT id FROM products WHERE name = 'Худи с капюшоном'),    'L',  'серый',   'HOD-L-GRY',     3),
    ((SELECT id FROM products WHERE name = 'Худи с капюшоном'),    'M',  'чёрный',  'HOD-M-BLK',     9),
    ((SELECT id FROM products WHERE name = 'Джинсы прямого кроя'), '32', 'синий',   'JNS-S-32-BLU',  5),
    ((SELECT id FROM products WHERE name = 'Джинсы прямого кроя'), '34', 'синий',   'JNS-S-34-BLU',  4),
    ((SELECT id FROM products WHERE name = 'Джинсы mom fit'),      '28', 'синий',   'JNS-M-28-BLU',  6),
    ((SELECT id FROM products WHERE name = 'Джинсы mom fit'),      '30', 'синий',   'JNS-M-30-BLU',  2),
    ((SELECT id FROM products WHERE name = 'Куртка-бомбер'),       'M',  'чёрный',  'JKT-B-M-BLK',   3),
    ((SELECT id FROM products WHERE name = 'Куртка-бомбер'),       'L',  'чёрный',  'JKT-B-L-BLK',   2),
    ((SELECT id FROM products WHERE name = 'Куртка стёганая'),     'S',  'бежевый', 'JKT-Q-S-BGE',   2),
    ((SELECT id FROM products WHERE name = 'Куртка стёганая'),     'M',  'бежевый', 'JKT-Q-M-BGE',   3),
    ((SELECT id FROM products WHERE name = 'Свитшот'),             'S',  'серый',   'SWT-S-GRY',     8),
    ((SELECT id FROM products WHERE name = 'Свитшот'),             'M',  'серый',   'SWT-M-GRY',     5);

INSERT INTO product_images (product_id, storage_key, color, sort_order) VALUES
    ((SELECT id FROM products WHERE name = 'Футболка оверсайз'), 'products/tshirt-oversize-black-1.jpg', 'чёрный', 0),
    ((SELECT id FROM products WHERE name = 'Футболка оверсайз'), 'products/tshirt-oversize-black-2.jpg', 'чёрный', 1),
    ((SELECT id FROM products WHERE name = 'Худи с капюшоном'),  'products/hoodie-grey-1.jpg',           'серый',  0);

-- Заказы: суммы совпадают с суммой позиций
INSERT INTO orders (user_id, status, total_amount, delivery_method, delivery_address, contact_phone, created_at) VALUES
    ((SELECT id FROM users WHERE email = 'anna@example.com'), 'delivered', 7770.00, 'courier', 'Москва, ул. Тверская, д. 10, кв. 5', '+79001112233', now() - interval '20 days'),
    ((SELECT id FROM users WHERE email = 'max@example.com'),  'paid',      4780.00, 'pickup',  'Пункт выдачи, Москва, Вернадского, 78', '+79002223344', now() - interval '3 days'),
    ((SELECT id FROM users WHERE email = 'anna@example.com'), 'new',       2990.00, 'courier', 'Москва, ул. Тверская, д. 10, кв. 5', '+79001112233', now() - interval '1 hour'),
    ((SELECT id FROM users WHERE email = 'ilya@example.com'), 'cancelled', 6990.00, 'courier', 'Москва, Ленинский пр., д. 44',        '+79003334455', now() - interval '7 days');

INSERT INTO order_items (order_id, variant_id, quantity, price_at_purchase) VALUES
    ((SELECT o.id FROM orders o JOIN users u ON u.id = o.user_id WHERE u.email = 'anna@example.com' AND o.status = 'delivered'),
     (SELECT id FROM product_variants WHERE sku = 'TSH-O-M-BLK'), 2, 1590.00),
    ((SELECT o.id FROM orders o JOIN users u ON u.id = o.user_id WHERE u.email = 'anna@example.com' AND o.status = 'delivered'),
     (SELECT id FROM product_variants WHERE sku = 'JNS-M-28-BLU'), 1, 4590.00),
    ((SELECT o.id FROM orders o JOIN users u ON u.id = o.user_id WHERE u.email = 'max@example.com'),
     (SELECT id FROM product_variants WHERE sku = 'TSH-B-M-WHT'), 1, 1290.00),
    ((SELECT o.id FROM orders o JOIN users u ON u.id = o.user_id WHERE u.email = 'max@example.com'),
     (SELECT id FROM product_variants WHERE sku = 'HOD-M-GRY'), 1, 3490.00),
    ((SELECT o.id FROM orders o JOIN users u ON u.id = o.user_id WHERE u.email = 'anna@example.com' AND o.status = 'new'),
     (SELECT id FROM product_variants WHERE sku = 'SWT-S-GRY'), 1, 2990.00),
    ((SELECT o.id FROM orders o JOIN users u ON u.id = o.user_id WHERE u.email = 'ilya@example.com'),
     (SELECT id FROM product_variants WHERE sku = 'JKT-B-M-BLK'), 1, 6990.00);

INSERT INTO payments (order_id, provider_payment_id, amount, status, created_at, paid_at)
SELECT o.id,
       CASE o.status WHEN 'new' THEN 'test-pay-0003' WHEN 'cancelled' THEN 'test-pay-0004'
                     WHEN 'paid' THEN 'test-pay-0002' ELSE 'test-pay-0001' END,
       o.total_amount,
       CASE o.status WHEN 'new' THEN 'pending' WHEN 'cancelled' THEN 'cancelled' ELSE 'succeeded' END,
       o.created_at,
       CASE WHEN o.status IN ('paid', 'delivered') THEN o.created_at + interval '2 minutes' END
FROM orders o;

INSERT INTO favorites (user_id, product_id) VALUES
    ((SELECT id FROM users WHERE email = 'anna@example.com'), (SELECT id FROM products WHERE name = 'Худи с капюшоном')),
    ((SELECT id FROM users WHERE email = 'anna@example.com'), (SELECT id FROM products WHERE name = 'Куртка стёганая')),
    ((SELECT id FROM users WHERE email = 'max@example.com'),  (SELECT id FROM products WHERE name = 'Джинсы прямого кроя'));

INSERT INTO reviews (user_id, product_id, rating, body) VALUES
    ((SELECT id FROM users WHERE email = 'anna@example.com'), (SELECT id FROM products WHERE name = 'Футболка оверсайз'), 5, 'Ткань плотная, сидит свободно, как я и хотела.'),
    ((SELECT id FROM users WHERE email = 'max@example.com'),  (SELECT id FROM products WHERE name = 'Футболка базовая'),  4, 'Хорошая, но после первой стирки чуть села.');

INSERT INTO cart_items (user_id, variant_id, quantity) VALUES
    ((SELECT id FROM users WHERE email = 'ilya@example.com'), (SELECT id FROM product_variants WHERE sku = 'JKT-B-L-BLK'), 1),
    ((SELECT id FROM users WHERE email = 'ilya@example.com'), (SELECT id FROM product_variants WHERE sku = 'HOD-L-GRY'),   1);
