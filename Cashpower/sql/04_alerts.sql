-- PLANNED, not used by the web app yet: low-units warnings.
USE cash_power_guard;

CREATE TABLE IF NOT EXISTS alert_prefs (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  user_id    INT NOT NULL,
  meter_id   INT NOT NULL,
  channel    VARCHAR(5) NOT NULL DEFAULT 'email',    -- email / sms
  days_left  INT NOT NULL DEFAULT 3,                 -- warn when this many days or fewer remain
  enabled    TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE (user_id, meter_id),
  FOREIGN KEY (user_id)  REFERENCES users(id)  ON DELETE CASCADE,
  FOREIGN KEY (meter_id) REFERENCES meters(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS alert_log (
  id       INT AUTO_INCREMENT PRIMARY KEY,
  user_id  INT NOT NULL,
  meter_id INT NOT NULL,
  channel  VARCHAR(5) NOT NULL,
  sent_at  VARCHAR(32) NOT NULL,
  FOREIGN KEY (user_id)  REFERENCES users(id)  ON DELETE CASCADE,
  FOREIGN KEY (meter_id) REFERENCES meters(id) ON DELETE CASCADE
) ENGINE=InnoDB;
