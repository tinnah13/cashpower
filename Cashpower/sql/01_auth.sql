-- Accounts, one-time codes (OTP) and remembered devices.
USE cash_power_guard;

CREATE TABLE IF NOT EXISTS users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  uid           VARCHAR(12)  UNIQUE,                 -- CPG-000001, shown to the person
  name          VARCHAR(120) NOT NULL,
  phone         VARCHAR(10)  NOT NULL UNIQUE,        -- one account per phone number
  email         VARCHAR(255) NOT NULL,
  acct_type     VARCHAR(20)  NOT NULL,               -- household / business / landlord
  pw_hash       VARCHAR(255) NOT NULL,               -- never the password itself
  lang          VARCHAR(2)   DEFAULT 'en',           -- en / fr / rw
  failed        INT          DEFAULT 0,              -- wrong passwords in a row
  locked_until  VARCHAR(32),
  created       VARCHAR(32)  NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS otps (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  phone      VARCHAR(10) NOT NULL,
  purpose    VARCHAR(10) NOT NULL,                   -- signup / login / reset
  code_hash  VARCHAR(64) NOT NULL,                   -- hash of the 6 digits, never the digits
  expires    VARCHAR(32) NOT NULL,                   -- 5 minutes after created
  tries      INT DEFAULT 0,                          -- locked after 5
  used       INT DEFAULT 0,
  created    VARCHAR(32) NOT NULL,
  INDEX (phone, purpose)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS devices (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  user_id     INT NOT NULL,
  token_hash  VARCHAR(64) NOT NULL UNIQUE,           -- the browser keeps the token, we keep its hash
  label       VARCHAR(80),
  expires     VARCHAR(32) NOT NULL,                  -- 30 days
  created     VARCHAR(32) NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;
