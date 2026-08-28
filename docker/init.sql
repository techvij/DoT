-- Seed data for DoT local development / demo.
-- Intentionally triggers several check failures so the tool shows value on first run.

CREATE TABLE IF NOT EXISTS orders (
    order_id    INTEGER,
    customer_id INTEGER,
    status      VARCHAR(50),
    amount      NUMERIC(10, 2),
    created_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    event_id   SERIAL PRIMARY KEY,
    event_type VARCHAR(100),
    user_id    INTEGER,
    created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id SERIAL PRIMARY KEY,
    order_id   INTEGER,
    amount     NUMERIC(10, 2),
    created_at TIMESTAMP
);

-- orders: ~5% null status (triggers null_rate), duplicate order_ids (triggers duplicate),
--         only 800 rows (triggers row_count min_rows: 1000)
INSERT INTO orders (order_id, customer_id, status, amount, created_at)
SELECT
    -- Every 20th row reuses the previous id — produces ~5% duplicates
    CASE WHEN gs % 20 = 0 THEN gs - 1 ELSE gs END                        AS order_id,
    (gs % 100) + 1                                                        AS customer_id,
    CASE WHEN gs % 18 = 0 THEN NULL ELSE 'completed' END                  AS status,
    ROUND((RANDOM() * 490 + 10)::NUMERIC, 2)                             AS amount,
    NOW() - (RANDOM() * INTERVAL '2 days')                               AS created_at
FROM GENERATE_SERIES(1, 800) gs;

-- events: all timestamps 18–24 hours old (triggers freshness max_age_hours: 6)
INSERT INTO events (event_type, user_id, created_at)
SELECT
    CASE (gs % 3)
        WHEN 0 THEN 'page_view'
        WHEN 1 THEN 'click'
        ELSE 'purchase'
    END                                                                   AS event_type,
    (gs % 100) + 1                                                        AS user_id,
    NOW() - INTERVAL '18 hours' - (RANDOM() * INTERVAL '6 hours')       AS created_at
FROM GENERATE_SERIES(1, 1200) gs;

-- payments: one negative amount row (triggers value_range min: 0)
INSERT INTO payments (order_id, amount, created_at)
SELECT
    gs                                                                    AS order_id,
    CASE WHEN gs = 500 THEN -50.00
         ELSE ROUND((RANDOM() * 800 + 20)::NUMERIC, 2)
    END                                                                   AS amount,
    NOW() - (RANDOM() * INTERVAL '3 days')                               AS created_at
FROM GENERATE_SERIES(1, 900) gs;
