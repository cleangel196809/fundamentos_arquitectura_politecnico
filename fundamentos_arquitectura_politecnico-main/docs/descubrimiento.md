# Descubrimiento de servicios en PiShop (P09)

## ¿Cliente o servidor?

- **Del lado del cliente**: el cliente consulta el registro (Consul) y elige la instancia él mismo.
  - Ventajas: sin un salto de red extra, el cliente puede aplicar su propia política de balanceo.
  - Desventajas: cada servicio necesita la lógica de consulta y balanceo; más acoplamiento al registro.
- **Del lado del servidor**: el cliente llama a un intermediario (balanceador o gateway) que consulta el registro y reenvía.
  - Ventajas: los clientes no conocen el registro; la lógica vive en un solo lugar.
  - Desventajas: un salto adicional y un componente más que puede fallar o ser cuello de botella.

## Decisión para PiShop

Se usa un enfoque **híbrido, con resolución del lado del cliente apoyada en un servicio**: `descubridor-service` encapsula la consulta a Consul (solo instancias `passing`) y devuelve una instancia por round-robin; el cliente (por ejemplo `checkout-bff`) llama a esa instancia directamente. Así los clientes no repiten la lógica de Consul ni de balanceo, y el tráfico de negocio no pasa por el descubridor.

Cada servicio se registra al arrancar (`registro.py`, desde el `lifespan`) con un chequeo HTTP a `/health/live` cada 10 s, y Consul lo retira del conjunto `passing` si deja de responder.
