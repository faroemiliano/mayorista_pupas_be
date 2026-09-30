# Dux como fuente de stock

La tienda conserva de WordPress la presentación comercial (nombre, descripción,
categorías, imágenes y variantes). Dux es la única fuente del stock total y de
los precios después de vincular cada producto. Los talles pertenecen a la tienda.

## Reglas de seguridad

- Con `DUX_SINCRONIZACION_HABILITADA=false` se mantiene el stock temporal de
  WordPress durante la transición.
- Con `DUX_SINCRONIZACION_HABILITADA=true` sólo cuenta stock real de Dux. Si
  `DUX_ID_DEPOSITO` está configurado, sólo cuenta ese depósito; otros depósitos
  y el depósito temporal `-1` de WordPress no abastecen la web.
- Un producto WordPress que no esté vinculado permanece visible pero sin stock
  vendible en modo Dux. Esto evita vender inventario viejo.
- Dux nunca crea ni modifica talles. La administración distribuye el stock
  total entre los talles de la página, y el carrito limita esa distribución por
  el total vigente de Dux.
- Un producto vinculado que desaparece del catálogo completo de Dux se
  deshabilita.

## Puesta en marcha

1. Mantener desactivada la sincronización mientras se concilian los catálogos.
2. Generar el informe con
   `POST /api/admin/migracion-wordpress/conciliacion-productos/generar` y seguir
   el proceso con `GET .../conciliacion-productos/ejecucion`.
3. Revisar el resumen y aplicar las coincidencias exactas con
   `POST .../conciliacion-productos/aplicar-seguras` enviando
   `{"confirmar": true}`. La operación fusiona el duplicado Dux dentro del
   producto WordPress y conserva las referencias de pedidos y reservas.
4. Resolver manualmente los casos dudosos y los productos sin coincidencia con
   `POST .../conciliacion-productos/vincular`. Los listados paginados
   `dudosos`, `solo-wordpress` y `solo-dux` permiten elegir cualquier pareja
   incluida en el informe.
5. Ejecutar la auditoría remota con
   `POST /api/admin/configuracion/dux/comparar-stock` y consultar el resultado
   en `GET /api/admin/configuracion/dux/auditoria-stock`.
6. Cuando la auditoría no reporte productos web sin vínculo, configurar
   `DUX_SINCRONIZACION_HABILITADA=true`, desplegar y ejecutar inmediatamente
   `POST /api/admin/productos/sincronizar`.
7. Verificar que el estado en `GET /api/admin/productos/sincronizacion` sea
   `completada` antes de anunciar el cambio.

`DUX_ESCRITURA_HABILITADA` es independiente: habilita altas de clientes y
pedidos en Dux, pero no decide de dónde sale el stock del catálogo. Para enviar
cada pedido confirmado automáticamente, configurar además
`DUX_ENVIO_AUTOMATICO_PEDIDOS_HABILITADO=true` y
`DUX_ID_PERSONAL_PEDIDOS_WEB` con un ID incluido en `DUX_PERSONALES_PEDIDOS`.
El pedido queda reservado de inmediato en la tienda; si Dux rechaza el envío,
queda marcado con error para reintentar desde administración.

## Operación recurrente

El catálogo público usa un snapshot local para responder rápido; no consulta
Dux en cada visita. Por eso el comando

```bash
python -m app.scripts.sincronizar_dux
```

debe ejecutarse con un scheduler externo y alertar ante fallos. Antes de elegir
la frecuencia hay que considerar que un pedido web mantiene una reserva local,
pero Dux no conoce esa reserva hasta que el pedido se envía. Si existen otros
canales vendiendo el mismo depósito, conviene enviar el pedido a Dux lo antes
posible y sincronizar nuevamente después. Dux documenta que el impacto de un
pedido puede demorar aproximadamente cinco minutos; por eso las reservas
enviadas conservan un margen local configurable antes de reconciliarse
(`DUX_RECONCILIACION_RESERVA_MINUTOS`, 10 minutos por defecto).

No se debe volver a importar stock WordPress como tarea periódica. La
reconversión de contenido está protegida para no pisar stock ni precios de un
producto ya vinculado a Dux.
