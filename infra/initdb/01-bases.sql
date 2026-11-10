-- =============================================================================
-- Paso 1 de la inicialización de PostgreSQL 17 (lo ejecuta la imagen oficial
-- la PRIMERA vez que arranca con el volumen vacío).
--
-- Una base privada por contexto acotado: nadie lee la base de otro servicio
-- (regla de la semana 1, antídoto contra el "monolito distribuido").
--
--   pg_catalogo    -> catalogo-service       (productos)
--   pg_inventario  -> inventario-service     (existencias y reservas)
--   pg_pedidos     -> pedidos-service        (pedidos + tabla outbox)
--   pg_pagos       -> pagos-service          (cobros y reembolsos)
--   pg_notif       -> notificaciones-service (mensajes enviados al cliente)
--   pg_reportes    -> reportes-service       (proyección CQRS de ventas)
-- =============================================================================
CREATE DATABASE pg_catalogo;
CREATE DATABASE pg_inventario;
CREATE DATABASE pg_pedidos;
CREATE DATABASE pg_pagos;
CREATE DATABASE pg_notif;
CREATE DATABASE pg_reportes;
