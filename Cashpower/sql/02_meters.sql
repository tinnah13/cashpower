-- Meters and the people allowed to see them.
USE cash_power_guard;

CREATE TABLE IF NOT EXISTS meters (
  id        INT AUTO_INCREMENT PRIMARY KEY,
  meter_no  VARCHAR(11) NOT NULL UNIQUE,             -- 11 digits, one owner per meter
  nickname  VARCHAR(30) NOT NULL,
  owner_id  INT NOT NULL,
  created   VARCHAR(32) NOT NULL,
  FOREIGN KEY (owner_id) REFERENCES users(id)
) ENGINE=InnoDB;

-- Keyed by phone number so an invitation works before the person has signed up.
CREATE TABLE IF NOT EXISTS access (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  meter_id    INT NOT NULL,
  phone       VARCHAR(10) NOT NULL,
  role        VARCHAR(4)  NOT NULL,                  -- view / add
  status      VARCHAR(8)  NOT NULL,                  -- pending / active
  invited_by  INT NOT NULL,
  created     VARCHAR(32) NOT NULL,
  UNIQUE (meter_id, phone),
  CHECK (role IN ('view','add')),
  CHECK (status IN ('pending','active')),
  FOREIGN KEY (meter_id) REFERENCES meters(id) ON DELETE CASCADE
) ENGINE=InnoDB;
