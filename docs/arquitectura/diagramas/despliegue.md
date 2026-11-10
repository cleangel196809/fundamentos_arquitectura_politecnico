# Diagrama de Despliegue de Infraestructura y Redes

| Metadato | Detalle |
| :--- | :--- |
| **Rol / Autor** | P11 — Arquitecto de Software |
| **Proyecto** | `fundamentos_arquitectura_politecnico` |
| **Topología** | Clúster de Contenedores Docker / Redes Aisladas y Volúmenes Persistentes |

---

## 1. Descripción de la Topología de Despliegue

La plataforma se despliega como un clúster multicontenedor gobernado por `docker-compose.yml`, estructurado en cuatro zonas de aislamiento de red:
1. **Zona Perimetral (`red-publica`):** Expone únicamente el puerto `8000` (`api-publica`) hacia el exterior para recibir el tráfico de clientes y compradores.
2. **Zona de Cómputo Interna (`red-interna`):** Conecta los microservicios de aplicación (Roles P01 a P10) y el broker RabbitMQ (`5672`). Ningún microservicio expone puertos de persistencia hacia el exterior.
3. **Zonas de Persistencia Aisladas (`red-datos-*` con `internal: true`):** Cada base de datos PostgreSQL se ejecuta en su propia red interna sin salida al exterior ni acceso entre bases de datos distintas, garantizando físicamente el principio *Database-per-Service*.
4. **Almacenamiento Persistente (Docker Named Volumes):** Cada motor de base de datos monta su directorio `/var/lib/postgresql/data` en un volumen dedicado (`pedidos_data`, `pagos_data`, etc.), asegurando que el reinicio o actualización de contenedores no provoque pérdida de información.

---

## 2. Diagrama de Despliegue en Mermaid

```mermaid
flowchart TD
    %% Estilos
    classDef client fill:#e2e3e5,stroke:#383d41,stroke-width:2px;
    classDef ingress fill:#cfe2ff,stroke:#084298,stroke-width:2px;
    classDef service fill:#d1e7dd,stroke:#0f5132,stroke-width:1.5px;
    classDef db fill:#cff4fc,stroke:#055160,stroke-width:2px;
    classDef broker fill:#ffe5d0,stroke:#d9480f,stroke-width:2px;
    classDef ext fill:#f8d7da,stroke:#842029,stroke-width:2px,stroke-dasharray: 4 4;

    subgraph DispositivoCliente ["Dispositivo del Cliente"]
        BrowserApp["Cliente Web / Móvil\n(React / SPA)"]:::client
    end

    subgraph HostDocker ["Host de Ejecución Docker Engine"]
        
        subgraph DMZ ["Red Pública Perimetral (red-publica)"]
            ApiPublica["api-publica [P07]\n(Port 8000:8000)"]:::ingress
        end

        subgraph RedInterna ["Red de Microservicios (red-interna)"]
            BFF["checkout-bff [P06]\n(Port 8080)"]:::service
            Catalogo["catalogo-service [P01]\n(Port 8001)"]:::service
            Inventario["inventario-service [P02]\n(Port 8002)"]:::service
            Pedidos["pedidos-service [P03]\n(Port 8003)"]:::service
            Pagos["pagos-service [P04]\n(Port 8004)"]:::service
            Notif["notificaciones-service [P05]\n(Port 8005)"]:::service
            Reportes["reportes-service [P10]\n(Port 8006)"]:::service
            Config["config-service [P08]\n(Port 8010)"]:::service
            Descubridor["descubridor-service [P09]\n(Port 8090)"]:::service
        end

        subgraph BrokerZone ["Mensajería y Eventos"]
            RabbitMQ["RabbitMQ Broker\n(Ports: 5672 AMQP / 15672 UI)"]:::broker
        end

        subgraph DataLayer ["Capa de Persistencia Aislada (Database-per-Service)"]
            CatDB[("catalogo-db\n(catalogo_data)")]:::db
            InvDB[("inventario-db\n(inventario_data)")]:::db
            PedDB[("pedidos-db\n(pedidos_data)")]:::db
            PagDB[("pagos-db\n(pagos_data)")]:::db
            NotDB[("notificaciones-db\n(notificaciones_data)")]:::db
            RepDB[("reportes-db\n(reportes_data)")]:::db
            CfgDB[("config-db\n(config_data)")]:::db
        end
    end

    subgraph ExternalCloud ["Servicios Externos Cloud"]
        PasarelaExt["Pasarela de Pagos Externa\n(Stripe / PSE / Simulador Bancario)"]:::ext
        EmailCloud["Proveedor de Email Cloud\n(SendGrid / Twilio)"]:::ext
    end

    %% Enlaces de Red
    BrowserApp -->|"HTTPS / Port 8000"| ApiPublica
    BrowserApp -->|"HTTPS / Port 8080"| BFF

    ApiPublica -->|"HTTP"| BFF
    BFF -->|"HTTP: 8003"| Pedidos
    BFF -->|"HTTP: 8002"| Inventario
    BFF -->|"HTTP: 8001"| Catalogo

    %% Conexiones exclusivas a DB (Database-per-Service)
    Catalogo --- CatDB
    Inventario --- InvDB
    Pedidos --- PedDB
    Pagos --- PagDB
    Notif --- NotDB
    Reportes --- RepDB
    Config --- CfgDB

    %% Conexiones con RabbitMQ
    Pedidos <-->|"AMQP Eventos Saga"| RabbitMQ
    Inventario <-->|"AMQP Reservas"| RabbitMQ
    Pagos <-->|"AMQP Cobros"| RabbitMQ
    RabbitMQ -->|"Consumo Eventos"| Notif
    RabbitMQ -->|"Consumo Eventos"| Reportes

    %% Integraciones Externas
    Pagos -->|"HTTPS REST (Capa ACL)"| PasarelaExt
    Notif -->|"HTTPS API"| EmailCloud
```

---

## 3. Código Fuente Versionado
El diagrama de despliegue se encuentra versionado también en formato PlantUML en [`despliegue.puml`](file:///c:/Users/LENOVO/Documents/SimuladorTrafico/docs/arquitectura/diagramas/despliegue.puml).
