-- ============================================================
-- DWG EMS-05 REV A – Creación de la base de datos en MySQL
-- Ejecutar UNA vez en MySQL Workbench o en la consola:
--     mysql -u root -p < sql/crear_base_mysql.sql
-- Las TABLAS las crea automáticamente el backend al arrancar
-- (SQLAlchemy create_all), junto con la flota y los datos demo.
-- ============================================================

CREATE DATABASE IF NOT EXISTS sysemerg_v2
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- (Opcional) usuario dedicado en lugar de root: quite los guiones de
-- las 3 líneas siguientes, cambie la contraseña y ponga en el .env:
-- DATABASE_URL=mysql+pymysql://ems_app:SU_CLAVE@localhost:3306/sysemerg_v2?charset=utf8mb4
-- CREATE USER IF NOT EXISTS 'ems_app'@'localhost' IDENTIFIED BY 'SU_CLAVE';
-- GRANT ALL PRIVILEGES ON sysemerg_v2.* TO 'ems_app'@'localhost';
-- FLUSH PRIVILEGES;

-- Para empezar de cero (borra todos los datos):
-- DROP DATABASE sysemerg_v2;  y vuelva a ejecutar este script.
