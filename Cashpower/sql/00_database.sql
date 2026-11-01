-- Cash Power Guard: database (MySQL 8). Run the files in order: 00, 01, 02, 03, 04, 05.
--   mysql -u root -p < 00_database.sql   (then the others, or use: SOURCE 01_auth.sql; ...)
-- The web app also creates the tables by itself (SQLite by default), so these files are for MySQL / the report.
CREATE DATABASE IF NOT EXISTS cash_power_guard CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE cash_power_guard;
