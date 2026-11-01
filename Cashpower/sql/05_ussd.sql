-- PLANNED, not used by the web app yet: phones without internet (USSD menu).
USE cash_power_guard;

CREATE TABLE IF NOT EXISTS ussd_sessions (
  session_id  VARCHAR(64) PRIMARY KEY,               -- id sent by the telecom operator
  phone       VARCHAR(10) NOT NULL,
  state       VARCHAR(30) NOT NULL DEFAULT 'menu',   -- where the person is in the menu
  data        VARCHAR(255),
  updated     VARCHAR(32) NOT NULL,
  INDEX (phone)
) ENGINE=InnoDB;
