# Registro y descubrimiento en PiShop Cloud (P09)

## Qué hay implementado

- **Auto-registro:** cada servicio, en su `lifespan`, se registra en Consul con su IP de contenedor, su puerto y un *health check* HTTP a `/health/ready` cada 10 s (`app/registro_consul.py`). Al apagarse se da de baja; si muere de golpe, Consul lo elimina tras 1 minuto en estado crítico.
- **descubridor-service (8090):** consulta a Consul y responde la lista de servicios, las instancias sanas (`passing`) y una URL elegida por **round-robin**.
- **El flujo de compra usa el DNS de Docker Compose:** el BFF llama a `http://catalogo-service:8001` (nombre lógico, nunca IP). Docker reparte entre réplicas del mismo servicio.

## Cliente vs servidor

| | Lado del cliente (Consul + descubridor) | Lado del servidor (DNS de Compose, Traefik, Kubernetes Service) |
|---|---|---|
| Quién elige la instancia | el que llama | un intermediario |
| Ventajas | sin salto extra; el cliente puede usar su propio algoritmo de balanceo | el código no sabe nada del registro; sirve para cualquier lenguaje |
| Desventajas | cada cliente debe implementar la lógica y manejar la caché | un componente más que puede fallar o volverse cuello de botella |

**Decisión para PiShop:** el flujo crítico (BFF → core) usa descubrimiento del lado del servidor (DNS de Compose) porque es más simple y no añade llamadas en la ruta de la compra. Consul + descubridor quedan para observación (UI de Consul) y para la demostración del reto 4.1. En la semana 5, Traefik toma el papel de balanceador del lado del servidor.

## Evidencia

```bat
docker compose up -d --scale catalogo-service=3
:: (quite antes el "ports" de catalogo-service o use el perfil seguro: 3 réplicas no pueden publicar el mismo puerto)
curl http://localhost:8090/v1/servicios
curl http://localhost:8090/v1/servicios/catalogo-service/instancias
curl http://localhost:8090/v1/servicios/catalogo-service/resolver    (repítalo: rota entre instancias)
```
