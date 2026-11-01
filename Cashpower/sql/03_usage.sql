-- Purchases, meter readings and the activity log the owner sees.
USE cash_power_guard;

CREATE TABLE IF NOT EXISTS entries (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  meter_id   INT NOT NULL,
  user_id    INT NOT NULL,                           -- who recorded it
  kind       VARCHAR(8) NOT NULL,                    -- purchase / reading
  day        VARCHAR(10) NOT NULL,                   -- YYYY-MM-DD
  rwf        INT,                                    -- money paid (purchases only)
  kwh        DOUBLE NOT NULL,                        -- units bought, or units left on the meter
  estimated  INT DEFAULT 0,                          -- 1 = calculated from the tariff, 0 = copied from the receipt
  created    VARCHAR(32) NOT NULL,
  CHECK (kind IN ('purchase','reading')),
  FOREIGN KEY (meter_id) REFERENCES meters(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id)  REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS activity (
  id        INT AUTO_INCREMENT PRIMARY KEY,
  meter_id  INT NOT NULL,
  user_id   INT,
  action    VARCHAR(30) NOT NULL,                    -- viewed, added_purchase, invited, accepted, removed ...
  detail    VARCHAR(255),
  ts        VARCHAR(32) NOT NULL,
  INDEX (meter_id, id),
  FOREIGN KEY (meter_id) REFERENCES meters(id) ON DELETE CASCADE
) ENGINE=InnoDB;
