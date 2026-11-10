"""
Script para generar las imágenes renderizadas SVG de los diagramas C4 Nivel 1 y Nivel 2
Garantiza que el repositorio cuente con las imágenes renderizadas vectoriales directamente visualizables en GitHub/Docs
"""
import os

svg_nivel1 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 800" width="1100" height="800">
  <defs>
    <style>
      .title { font-family: 'Segoe UI', Arial, sans-serif; font-size: 20px; font-weight: bold; fill: #111; }
      .subtitle { font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; fill: #555; }
      .box-person { fill: #08427b; stroke: #052e56; stroke-width: 2; rx: 8; }
      .box-system { fill: #1168bd; stroke: #0b4884; stroke-width: 2; rx: 8; }
      .box-external { fill: #6c757d; stroke: #495057; stroke-width: 2; rx: 8; }
      .boundary { fill: #f8f9fa; stroke: #adb5bd; stroke-width: 2; stroke-dasharray: 6 4; rx: 12; }
      .text-title { font-family: 'Segoe UI', Arial, sans-serif; font-size: 15px; font-weight: bold; fill: #ffffff; text-anchor: middle; }
      .text-type { font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; fill: #e0e0e0; text-anchor: middle; }
      .text-desc { font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; fill: #f8f9fa; text-anchor: middle; }
      .line { stroke: #495057; stroke-width: 2; marker-end: url(#arrow); }
      .line-label { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.5px; fill: #212529; text-anchor: middle; background-color: #ffffff; }
      .legend-text { font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; fill: #333; }
    </style>
    <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#495057" />
    </marker>
  </defs>

  <!-- Canvas Background -->
  <rect width="1100" height="800" fill="#ffffff" />

  <!-- Título -->
  <text x="50" y="40" class="title">Diagrama de Contexto del Sistema (C4 Nivel 1)</text>
  <text x="50" y="62" class="subtitle">Ecosistema Digital Politécnico — Plataforma Distribuida de Comercio y Pagos (fundamentos_arquitectura_politecnico)</text>

  <!-- Boundary Institucional -->
  <rect x="350" y="110" width="400" height="420" class="boundary" />
  <text x="370" y="135" font-family="'Segoe UI', Arial, sans-serif" font-size="13px" font-weight="bold" fill="#6c757d">Ecosistema Institucional Politécnico</text>

  <!-- Personas (Izquierda y Arriba) -->
  <!-- Cliente -->
  <g transform="translate(60, 180)">
    <rect width="220" height="110" class="box-person" />
    <circle cx="110" cy="-18" r="14" fill="#08427b" stroke="#052e56" stroke-width="2" />
    <text x="110" y="32" class="text-title">Cliente / Comprador</text>
    <text x="110" y="48" class="text-type">[Persona]</text>
    <text x="110" y="70" class="text-desc">Usuario final que adquiere</text>
    <text x="110" y="86" class="text-desc">productos y realiza checkout</text>
  </g>

  <!-- Operador -->
  <g transform="translate(60, 370)">
    <rect width="220" height="110" class="box-person" />
    <circle cx="110" cy="-18" r="14" fill="#08427b" stroke="#052e56" stroke-width="2" />
    <text x="110" y="32" class="text-title">Operador / Finanzas</text>
    <text x="110" y="48" class="text-type">[Persona]</text>
    <text x="110" y="70" class="text-desc">Audita pedidos, pagos,</text>
    <text x="110" y="86" class="text-desc">cancelaciones y reportes</text>
  </g>

  <!-- Sistema Central -->
  <g transform="translate(410, 200)">
    <rect width="280" height="230" class="box-system" />
    <text x="140" y="40" class="text-title">Plataforma de Comercio</text>
    <text x="140" y="60" class="text-title">y Pagos Politécnico</text>
    <text x="140" y="82" class="text-type">[Software System - Microservicios]</text>
    <text x="140" y="115" class="text-desc">Orquesta la vitrina, checkout,</text>
    <text x="140" y="133" class="text-desc">reservas de inventario, sagas</text>
    <text x="140" y="151" class="text-desc">transaccionales y liquidación de pagos.</text>
    <text x="140" y="180" class="text-desc">Roles: P01 a P10 (Puertos 8000-8090)</text>
    <text x="140" y="200" class="text-desc">Gobernanza: P11 (Arquitecto)</text>
  </g>

  <!-- Sistemas Externos (Derecha) -->
  <!-- Pasarela de Pagos -->
  <g transform="translate(820, 150)">
    <rect width="220" height="100" class="box-external" />
    <text x="110" y="30" class="text-title">Pasarela de Pagos</text>
    <text x="110" y="48" class="text-type">[External System - Stripe / PSE / Sim]</text>
    <text x="110" y="68" class="text-desc">Autoriza débitos monetarios</text>
    <text x="110" y="84" class="text-desc">y emite tokens de cobro</text>
  </g>

  <!-- Proveedor Notificaciones -->
  <g transform="translate(820, 290)">
    <rect width="220" height="100" class="box-external" />
    <text x="110" y="30" class="text-title">Proveedor Notificaciones</text>
    <text x="110" y="48" class="text-type">[External System - SendGrid / Twilio]</text>
    <text x="110" y="68" class="text-desc">Envío de emails y SMS</text>
    <text x="110" y="84" class="text-desc">transaccionales al cliente</text>
  </g>

  <!-- ERP Legado -->
  <g transform="translate(820, 430)">
    <rect width="220" height="100" class="box-external" />
    <text x="110" y="30" class="text-title">ERP Financiero / DIAN</text>
    <text x="110" y="48" class="text-type">[External System - Legado]</text>
    <text x="110" y="68" class="text-desc">Facturación fiscal electrónica</text>
    <text x="110" y="84" class="text-desc">y asientos contables oficiales</text>
  </g>

  <!-- Líneas y Conexiones -->
  <!-- Cliente -> Sistema -->
  <path d="M 280 235 L 410 260" class="line" />
  <rect x="290" y="230" width="110" height="20" fill="#fff" rx="3" />
  <text x="345" y="244" class="line-label">POST /v1/checkout</text>

  <!-- Operador -> Sistema -->
  <path d="M 280 425 L 410 380" class="line" />
  <rect x="290" y="390" width="110" height="20" fill="#fff" rx="3" />
  <text x="345" y="404" class="line-label">GET /v1/reportes</text>

  <!-- Sistema -> Pasarela -->
  <path d="M 690 260 L 820 205" class="line" />
  <rect x="700" y="215" width="110" height="20" fill="#fff" rx="3" />
  <text x="755" y="229" class="line-label">HTTPS (vía Capa ACL)</text>

  <!-- Sistema -> Notificaciones -->
  <path d="M 690 320 L 820 335" class="line" />
  <rect x="710" y="315" width="95" height="20" fill="#fff" rx="3" />
  <text x="755" y="329" class="line-label">HTTPS / Webhook</text>

  <!-- Sistema -> ERP -->
  <path d="M 690 380 L 820 465" class="line" />
  <rect x="710" y="415" width="95" height="20" fill="#fff" rx="3" />
  <text x="755" y="429" class="line-label">SFTP / Batch</text>

  <!-- Notificaciones -> Cliente (Retorno) -->
  <path d="M 930 290 Q 930 90 200 90 L 170 160" class="line" stroke-dasharray="4 4" />
  <rect x="470" y="80" width="170" height="20" fill="#fff" rx="3" />
  <text x="555" y="94" class="line-label">Email / SMS de Confirmación</text>

  <!-- Leyenda C4 -->
  <g transform="translate(60, 600)">
    <rect x="0" y="0" width="980" height="150" fill="#f8f9fa" stroke="#dee2e6" rx="8" />
    <text x="20" y="25" font-family="'Segoe UI', Arial, sans-serif" font-size="13px" font-weight="bold" fill="#333">Convenciones y Metadatos C4 Nivel 1:</text>
    
    <rect x="30" y="45" width="24" height="24" fill="#08427b" rx="4" />
    <text x="65" y="62" class="legend-text">Persona (Usuario Interno o Externo del Sistema)</text>

    <rect x="30" y="80" width="24" height="24" fill="#1168bd" rx="4" />
    <text x="65" y="97" class="legend-text">Sistema de Software Central (fundamentos_arquitectura_politecnico)</text>

    <rect x="30" y="115" width="24" height="24" fill="#6c757d" rx="4" />
    <text x="65" y="132" class="legend-text">Sistema Externo (Pasarela Financiera, Notificaciones, ERP Legado)</text>

    <text x="600" y="62" class="legend-text"><b>Sondas de salud obligatorias:</b> /health/live, /health/ready, /health/startup</text>
    <text x="600" y="90" class="legend-text"><b>Gobernanza Arquitectónica:</b> P11 Arquitecto (Docs-as-Code)</text>
    <text x="600" y="118" class="legend-text"><b>Contrato Mínimo:</b> 10 Servicios enlazados con OpenAPI 3.0</text>
  </g>
</svg>
"""

svg_nivel2 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1350 1150" width="1350" height="1150">
  <defs>
    <style>
      .title { font-family: 'Segoe UI', Arial, sans-serif; font-size: 22px; font-weight: bold; fill: #111; }
      .subtitle { font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; fill: #555; }
      .box-person { fill: #08427b; stroke: #052e56; stroke-width: 2; rx: 8; }
      .box-container { fill: #1168bd; stroke: #0b4884; stroke-width: 2; rx: 8; }
      .box-db { fill: #2b78e4; stroke: #1952a5; stroke-width: 2; rx: 14; }
      .box-broker { fill: #ff6600; stroke: #cc5200; stroke-width: 2; rx: 8; }
      .box-external { fill: #6c757d; stroke: #495057; stroke-width: 2; rx: 8; }
      .boundary { fill: #fdfdfd; stroke: #0b4884; stroke-width: 2; stroke-dasharray: 6 4; rx: 12; }
      .sub-boundary { fill: #f4f6f9; stroke: #ced4da; stroke-width: 1.5; rx: 8; }
      .text-title { font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; font-weight: bold; fill: #ffffff; text-anchor: middle; }
      .text-type { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10px; fill: #e9ecef; text-anchor: middle; }
      .text-desc { font-family: 'Segoe UI', Arial, sans-serif; font-size: 9.5px; fill: #ffffff; text-anchor: middle; }
      .line { stroke: #495057; stroke-width: 1.8; marker-end: url(#arrow2); }
      .line-label { font-family: 'Segoe UI', Arial, sans-serif; font-size: 9px; fill: #111; text-anchor: middle; }
    </style>
    <marker id="arrow2" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#495057" />
    </marker>
  </defs>

  <rect width="1350" height="1150" fill="#ffffff" />

  <!-- Título -->
  <text x="40" y="35" class="title">Diagrama de Contenedores (C4 Nivel 2) — Plataforma Distribuida de Comercio y Pagos</text>
  <text x="40" y="58" class="subtitle">Arquitectura de Microservicios con Persistencia Aislada (Database-per-Service) y Puertos Oficiales (P01 - P10)</text>

  <!-- Boundary Principal -->
  <rect x="250" y="80" width="840" height="920" class="boundary" />
  <text x="270" y="105" font-family="'Segoe UI', Arial, sans-serif" font-size="14px" font-weight="bold" fill="#0b4884">Frontera del Sistema: fundamentos_arquitectura_politecnico</text>

  <!-- Actor Cliente -->
  <g transform="translate(30, 200)">
    <rect width="170" height="90" class="box-person" />
    <circle cx="85" cy="-14" r="12" fill="#08427b" stroke="#052e56" stroke-width="2" />
    <text x="85" y="26" class="text-title">Cliente Web/App</text>
    <text x="85" y="42" class="text-type">[Persona]</text>
    <text x="85" y="62" class="text-desc">Inicia checkout y compra</text>
  </g>

  <!-- Capa Ingress: API Pública (P07: 8000) y Checkout BFF (P06: 8080) -->
  <!-- API Pública -->
  <g transform="translate(290, 130)">
    <rect width="220" height="90" class="box-container" />
    <text x="110" y="24" class="text-title">api-publica [P07]</text>
    <text x="110" y="40" class="text-type">[Container: Port 8000]</text>
    <text x="110" y="60" class="text-desc">GET /v1/catalogo/productos</text>
    <text x="110" y="75" class="text-desc">POST /v1/compras</text>
  </g>

  <!-- Checkout BFF -->
  <g transform="translate(560, 130)">
    <rect width="220" height="90" class="box-container" />
    <text x="110" y="24" class="text-title">checkout-bff [P06]</text>
    <text x="110" y="40" class="text-type">[Container: Port 8080]</text>
    <text x="110" y="60" class="text-desc">POST /v1/checkout</text>
    <text x="110" y="75" class="text-desc">GET /v1/vitrina, estado</text>
  </g>

  <!-- Servicios Transaccionales Core -->
  <!-- Pedidos Service (P03: 8003) -->
  <g transform="translate(290, 290)">
    <rect width="220" height="90" class="box-container" />
    <text x="110" y="22" class="text-title">pedidos-service [P03]</text>
    <text x="110" y="38" class="text-type">[Container: Port 8003]</text>
    <text x="110" y="56" class="text-desc">POST /v1/pedidos | Saga Orquestador</text>
    <text x="110" y="72" class="text-desc">Outbox /v1/outbox/pendientes</text>
  </g>
  <!-- Pedidos DB -->
  <g transform="translate(560, 290)">
    <rect width="180" height="90" class="box-db" />
    <text x="90" y="25" class="text-title">pedidos-db</text>
    <text x="90" y="42" class="text-type">[PostgreSQL 16 - Port 5432]</text>
    <text x="90" y="65" class="text-desc">pedidos_db (Aislada)</text>
  </g>

  <!-- Pagos Service (P04: 8004) -->
  <g transform="translate(290, 420)">
    <rect width="220" height="90" class="box-container" />
    <text x="110" y="22" class="text-title">pagos-service [P04]</text>
    <text x="110" y="38" class="text-type">[Container: Port 8004]</text>
    <text x="110" y="56" class="text-desc">POST /v1/pagos | Capa ACL</text>
    <text x="110" y="72" class="text-desc">POST /_simulador/pasarela/cobrar</text>
  </g>
  <!-- Pagos DB -->
  <g transform="translate(560, 420)">
    <rect width="180" height="90" class="box-db" />
    <text x="90" y="25" class="text-title">pagos-db</text>
    <text x="90" y="42" class="text-type">[PostgreSQL 16 - Port 5432]</text>
    <text x="90" y="65" class="text-desc">pagos_db (Aislada)</text>
  </g>

  <!-- Inventario Service (P02: 8002) -->
  <g transform="translate(290, 550)">
    <rect width="220" height="90" class="box-container" />
    <text x="110" y="22" class="text-title">inventario-service [P02]</text>
    <text x="110" y="38" class="text-type">[Container: Port 8002]</text>
    <text x="110" y="56" class="text-desc">POST /v1/reservas | Stock SKU</text>
    <text x="110" y="72" class="text-desc">POST /v1/reservas/{id}/liberar</text>
  </g>
  <!-- Inventario DB -->
  <g transform="translate(560, 550)">
    <rect width="180" height="90" class="box-db" />
    <text x="90" y="25" class="text-title">inventario-db</text>
    <text x="90" y="42" class="text-type">[PostgreSQL 16 - Port 5432]</text>
    <text x="90" y="65" class="text-desc">inventario_db (Aislada)</text>
  </g>

  <!-- Catálogo Service (P01: 8001) -->
  <g transform="translate(290, 680)">
    <rect width="220" height="90" class="box-container" />
    <text x="110" y="22" class="text-title">catalogo-service [P01]</text>
    <text x="110" y="38" class="text-type">[Container: Port 8001]</text>
    <text x="110" y="56" class="text-desc">GET /v1/productos | SKUs</text>
    <text x="110" y="72" class="text-desc">PATCH /v1/productos/{sku}/publicar</text>
  </g>
  <!-- Catálogo DB -->
  <g transform="translate(560, 680)">
    <rect width="180" height="90" class="box-db" />
    <text x="90" y="25" class="text-title">catalogo-db</text>
    <text x="90" y="42" class="text-type">[PostgreSQL 16 - Port 5432]</text>
    <text x="90" y="65" class="text-desc">catalogo_db (Aislada)</text>
  </g>

  <!-- Servicios Soporte: Notificaciones (P05: 8005) y Reportes (P10: 8006) -->
  <!-- Notificaciones Service -->
  <g transform="translate(290, 810)">
    <rect width="220" height="85" class="box-container" />
    <text x="110" y="22" class="text-title">notificaciones-service [P05]</text>
    <text x="110" y="38" class="text-type">[Container: Port 8005]</text>
    <text x="110" y="56" class="text-desc">GET /v1/notificaciones</text>
    <text x="110" y="70" class="text-desc">POST /v1/notificaciones/prueba</text>
  </g>

  <!-- Reportes Service -->
  <g transform="translate(560, 810)">
    <rect width="220" height="85" class="box-container" />
    <text x="110" y="22" class="text-title">reportes-service [P10]</text>
    <text x="110" y="38" class="text-type">[Container: Port 8006]</text>
    <text x="110" y="56" class="text-desc">GET /v1/reportes/resumen</text>
    <text x="110" y="70" class="text-desc">CQRS Proyecciones de ventas</text>
  </g>

  <!-- Message Broker RabbitMQ (Columna Derecha) -->
  <g transform="translate(820, 290)">
    <rect width="230" height="350" class="box-broker" />
    <text x="115" y="40" class="text-title">RabbitMQ Broker</text>
    <text x="115" y="60" class="text-type">[AMQP 0-9-1 - Ports 5672/15672]</text>
    <text x="115" y="110" class="text-desc">Exchange: ecommerce.events</text>
    <text x="115" y="140" class="text-desc">Eventos de Saga Distribuida:</text>
    <text x="115" y="165" class="text-desc">• PedidoCreado</text>
    <text x="115" y="190" class="text-desc">• StockReservado / Fallido</text>
    <text x="115" y="215" class="text-desc">• PagoAprobado / Rechazado</text>
    <text x="115" y="240" class="text-desc">• CompensacionIniciada</text>
    <text x="115" y="265" class="text-desc">• PedidoCancelado</text>
    <text x="115" y="300" class="text-desc">Colas Dead-Letter (DLQ)</text>
  </g>

  <!-- Config & Descubridor (Abajo Derecha) -->
  <g transform="translate(820, 680)">
    <rect width="230" height="75" class="box-container" />
    <text x="115" y="24" class="text-title">config-service [P08]</text>
    <text x="115" y="40" class="text-type">[Port 8010 - config_db]</text>
    <text x="115" y="58" class="text-desc">Versiones y Rollback de Config</text>
  </g>

  <g transform="translate(820, 780)">
    <rect width="230" height="75" class="box-container" />
    <text x="115" y="24" class="text-title">descubridor-service [P09]</text>
    <text x="115" y="40" class="text-type">[Port 8090 - In-Memory Registry]</text>
    <text x="115" y="58" class="text-desc">Service Registry &amp; Resolver</text>
  </g>

  <!-- Sistemas Externos (Derecha Fuera de Boundary) -->
  <g transform="translate(1120, 420)">
    <rect width="200" height="90" class="box-external" />
    <text x="100" y="28" class="text-title">Simulador Pasarela</text>
    <text x="100" y="46" class="text-type">[External / Mock Bank]</text>
    <text x="100" y="66" class="text-desc">POST /_simulador/pasarela/cobrar</text>
  </g>

  <g transform="translate(1120, 810)">
    <rect width="200" height="85" class="box-external" />
    <text x="100" y="28" class="text-title">Proveedor Notif.</text>
    <text x="100" y="46" class="text-type">[SendGrid / Twilio]</text>
    <text x="100" y="66" class="text-desc">Despacho Email / SMS</text>
  </g>

  <!-- Conexiones Clave -->
  <!-- Cliente -> API Pública & BFF -->
  <path d="M 200 240 L 290 180" class="line" />
  <path d="M 200 260 L 560 175" class="line" />

  <!-- BFF a Pedidos, Inventario y Catálogo -->
  <path d="M 640 220 L 450 290" class="line" />
  <path d="M 670 220 L 450 550" class="line" />

  <!-- Database-per-service (Conexiones 1 a 1 a DB) -->
  <path d="M 510 335 L 560 335" class="line" />
  <path d="M 510 465 L 560 465" class="line" />
  <path d="M 510 595 L 560 595" class="line" />
  <path d="M 510 725 L 560 725" class="line" />

  <!-- Pagos Service a Pasarela Externa (Capa ACL) -->
  <path d="M 510 440 L 820 440" class="line" stroke-dasharray="3 3" />
  <path d="M 1050 465 L 1120 465" class="line" />
  <rect x="730" y="425" width="80" height="18" fill="#fff" rx="3" />
  <text x="770" y="438" class="line-label">Capa ACL</text>

  <!-- Publicación a RabbitMQ Broker -->
  <path d="M 510 360 L 820 360" class="line" />
  <path d="M 820 580 L 510 580" class="line" />

  <!-- Leyenda y Nota de Gobernanza -->
  <g transform="translate(40, 1020)">
    <rect width="1270" height="100" fill="#f8f9fa" stroke="#dee2e6" rx="8" />
    <text x="20" y="25" font-family="'Segoe UI', Arial, sans-serif" font-size="12px" font-weight="bold" fill="#333">Regla de Aptitud Arquitectónica (Fitness Function - P11):</text>
    <text x="20" y="50" font-family="'Segoe UI', Arial, sans-serif" font-size="11px" fill="#495057">1. <b>Database-per-Service:</b> Cada microservicio tiene conexión exclusiva a su base de datos (pedidos_db, pagos_db, inventario_db, catalogo_db, notificaciones_db, reportes_db, config_db). Prohibido compartir esquemas.</text>
    <text x="20" y="70" font-family="'Segoe UI', Arial, sans-serif" font-size="11px" fill="#495057">2. <b>Validación Automática:</b> El script <code>herramientas/validar_fronteras.py</code> analiza la persistencia en CI/CD y falla (exit code 1) si dos servicios comparten BD.</text>
    <text x="20" y="90" font-family="'Segoe UI', Arial, sans-serif" font-size="11px" fill="#495057">3. <b>Sondas de Salud:</b> Todos los servicios exponen <code>/health/live</code>, <code>/health/ready</code> y <code>/health/startup</code>. Contratos OpenAPI versionados.</text>
  </g>
</svg>
"""

os.makedirs(r"c:\Users\LENOVO\Documents\SimuladorTrafico\docs\arquitectura\c4", exist_ok=True)

with open(r"c:\Users\LENOVO\Documents\SimuladorTrafico\docs\arquitectura\c4\c4-nivel1-contexto.svg", "w", encoding="utf-8") as f:
    f.write(svg_nivel1)

with open(r"c:\Users\LENOVO\Documents\SimuladorTrafico\docs\arquitectura\c4\c4-nivel2-contenedores.svg", "w", encoding="utf-8") as f:
    f.write(svg_nivel2)

print("Rendered SVGs created successfully.")
