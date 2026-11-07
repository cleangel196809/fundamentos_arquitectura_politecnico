# Reto 3.1: ¿cuánto tiempo se cae PiShop Cloud? (P12)

Autora: Danixa Alexandra Herrera Nimisica · Paquete P12

## Cómo correrlo

```
python retos/semana03/disponibilidad.py
```

Funciona con Python 3.13 y no necesita instalar nada más.

## La idea en una frase

Para que un cliente pueda comprar, **7 piezas tienen que funcionar al mismo tiempo**. Si una sola falla, la compra falla. Por eso, aunque cada pieza sea muy buena, juntas fallan más que cada una por separado.

## Las 7 piezas (valores del reto 3.1 del profe)

| Pieza | Funciona el... |
|---|---|
| api-publica | 99,95 % del tiempo |
| checkout-bff | 99,90 % |
| catalogo-service | 99,90 % |
| inventario-service | 99,85 % |
| pedidos-service | 99,90 % |
| pagos-service | 99,70 % |
| pasarela externa (el banco) | 99,50 % |

## Las 3 fórmulas (están programadas en el script)

| Fórmula | Para qué sirve | En el código |
|---|---|---|
| `A = A1 × A2 × … × An` | **Serie:** todas deben funcionar, entonces se multiplican | `serie()` |
| `A = 1 − (1 − a)^n` | **Paralelo:** con n copias, basta con que una funcione | `paralelo()` |
| `(1 − A) × 8760` | Horas al año que el sistema está caído (un año tiene 8760 horas) | `horas_caida()` |

Ejemplo a mano con pagos y 2 copias: una copia falla el 0,003 del tiempo; las dos a la vez, 0,003 × 0,003 = 0,000009; entonces funciona 1 − 0,000009 = 0,999991.

## Tabla antes / después

| Escenario | Qué cambia | Funciona el... | Caído al año | Ahorro |
|---|---|---|---|---|
| **Antes** | Se multiplican las 7 piezas | 98,7065 % | 113,31 h (casi 5 días) | — |
| **M1** Copias de cada servicio | Las 6 piezas nuestras pasan a 2 copias; el banco queda igual | 99,4986 % | 43,93 h | 69,4 h |
| **M2** Segunda pasarela | Solo el banco cambia: 99,50 % → 99,9975 % | 99,2000 % | 70,08 h | 43,2 h |
| **M3** Cobrar después | Pagos y banco salen de la cadena; se multiplican 5 piezas | 99,5010 % | 43,71 h | 69,6 h |
| **M1 + M2 + M3** | Las tres juntas | 99,9995 % | 0,05 h (unos 3 minutos) | 113,3 h |

Nota sobre la última fila: con M3 el cobro ya no está en la cadena de la compra, así que el cálculo queda con las 5 piezas restantes, cada una con 2 copias. M1 y M2 siguen sirviendo para que el cobro que se hace después también falle menos.

## Las 3 mejoras explicadas

**M1: tener 2 copias de cada servicio (eje X del cubo de escalabilidad).**
El eje X del cubo significa "clonar": poner varias copias iguales del mismo servicio. Si una copia se cae, la otra sigue atendiendo, como un banco con dos cajas abiertas. El banco externo no se puede copiar porque no es nuestro. Ojo: solo funciona si las copias no se caen al mismo tiempo, por eso deben estar en lugares distintos.

**M2: tener una segunda pasarela de pago (redundancia en paralelo).**
El banco es la pieza más débil (99,50 %) y no la controlamos. Si contratamos un segundo proveedor de pagos, cuando uno falla se usa el otro. El cambio de proveedor se hace en el adaptador (ACL) de pagos-service.

**M3: cobrar después y no en el mismo instante (asíncrono, con saga + Outbox).**
El checkout guarda el pedido como "pendiente de pago" y le responde al cliente de inmediato. El cobro se hace unos segundos después:
- **Outbox** (bandeja de salida): junto con el pedido se guarda la nota "falta cobrar". Así el aviso no se pierde aunque pagos esté caído en ese momento.
- **Saga:** si después el cobro falla, se deshace lo anterior: se libera el producto reservado y se cancela el pedido. A eso se le llama compensación.

*¿Por qué el cobro puede esperar?* El cliente no necesita ver el cobro en el mismo segundo. Basta con confirmarle después por notificación.

*¿Qué riesgo asume el negocio?* Aceptamos un pedido sin saber todavía si el pago va a pasar. Si el banco lo rechaza, hay que cancelarlo, devolver el stock y avisarle al cliente, que puede quedar molesto.

## Conclusión

Siete piezas "muy buenas" en cadena dejan la tienda caída **113 horas al año**. Lo que más ayuda es tener copias (M1) o sacar el cobro de la cadena (M3). Con las tres mejoras juntas, la caída baja a unos minutos al año.

## Uso de IA generativa

Usé Claude (Anthropic) como apoyo para entender el tema y estructurar el script. Verifiqué a mano la multiplicación en serie, la fórmula de paralelo con pagos y las horas de caída, y comprobé los resultados corriendo el script.
