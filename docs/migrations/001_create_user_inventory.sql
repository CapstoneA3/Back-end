-- user_inventory: 사용자별 보유 식재료 인스턴스 (FIFO 차감 단위)
CREATE TABLE IF NOT EXISTS user_inventory (
    id          BIGSERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,
    ingredient_master_id BIGINT NOT NULL REFERENCES ingredient_master(id),
    quantity    NUMERIC NOT NULL DEFAULT 1,
    unit        VARCHAR(50),
    expire_date DATE NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_inventory_user_id
    ON user_inventory(user_id);

CREATE INDEX IF NOT EXISTS idx_user_inventory_expire_date
    ON user_inventory(user_id, expire_date ASC);
