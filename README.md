# Resumen de Reuniones IA — Batidos Pitaya

Herramienta de grabación de reuniones corporativas con **transcripción literal** y **resumen ejecutivo** generado por IA (Gemini).

> **Estado**: 🟢 En Producción (Desplegado en ERP y VPS)

---

## 🏗️ Arquitectura del Sistema

El flujo End-to-End se divide en tres componentes:

```text
ERP (Hostinger)                   API (Hostinger)                  VPS (DigitalOcean)
──────────────────────            ──────────────────────           ────────────────────────────
modulos/sistemas/                 api/resumen_reuniones_ia/        /opt/resumen-reuniones-ia/
resumen_reuniones.php  ────────▶  crear.php          ◀──────────▶  app/main.py (FastAPI)
(genera token, abre VPS)          obtener_por_token.php              app/audio.py (fragmentos)
                                  actualizar_estado.php              app/gemini_client.py
                                  guardar_resultado.php              app/static/ (UI grabación)
                                  obtener_key_gemini.php
                                  aprobar.php

BD MySQL (Hostinger)
  └── resumen_reuniones_ia (Tabla central de estados)
```

---

## 🛠️ Flujo de Grabación y Procesamiento

1. **Creación**: El usuario en el ERP (`resumen_reuniones.php`) crea una reunión. La API en Hostinger genera un token válido por 6 horas y devuelve el enlace al VPS.
2. **Setup y UI**: El ERP abre el enlace `reuniones.batidospitaya.com/?token=XYZ`. La interfaz (FastAPI Sirviendo `grabacion.js`) verifica el token llamando a `GET /api/info/{token}`.
3. **Grabación Continua**: Al presionar Empezar, el navegador graba el audio usando `MediaRecorder` y hace un `POST /api/fragmento/{token}` cada 60 segundos.
4. **Finalizar**: Al presionar Finalizar, se gatilla `POST /api/finalizar/{token}` que lanza un `Background Task` y retorna éxito inmediato para no bloquear el UI del usuario.
5. **Procesamiento de IA (Background)**:
   - `ffmpeg` concatena los fragmentos webm.
   - Sube el archivo de audio usando *Google Gemini Files API*.
   - Promptea a Gemini (flash) para que **primero genere una transcripción literal** y luego un **resumen ejecutivo** con formato rígido.
   - Guarda el Markdown resultante en la BD (`actualizar_estado.php`).
   - Borra el audio temporal de los servidores de Google Gemini por privacidad.
6. **Aprobación y Limpieza**: Desde el ERP, el usuario valida el resumen y (si está todo OK) le da Aprobar. Esto gatilla `DELETE /api/audio/{id}` en el VPS, **borrando definitivamente el audio del disco duro del VPS**.

---

## 🧩 Modificaciones y Correcciones Críticas (Julio 2026)

Para futuras referencias, ten en cuenta estos arreglos realizados en el sistema si surge un error similar:

1. **Idempotencia en Máquina de Estados**: El endpoint de actualización de estado (`/api/estado/` y el PHP `actualizar_estado.php`) fue modificado para ser **idempotente**. Si el navegador envía dos veces que está "grabando", ya no falla con un código 422, simplemente responde con éxito. Esto previene que errores de doble-clic o recargas de página interfieran con la BD.
2. **Transcripción Literal**: Gemini no guardaba la transcripción al principio, lo que impedía auditar los resúmenes. Ahora el Prompt maestro en `gemini_client.py` fuerza a la IA a escribir toda la transcripción en crudo bajo `## Transcripción` antes que el resumen. El frontend del ERP (con JavaScript) intercepta ese encabezado y lo coloca en un acordeón plegable para no saturar la pantalla.
3. **Validación de Token Flexible**: FastAPI verificaba exactamente `len == 48`. A veces el token llegaba distinto. Se aflojó la validación en `tokens.py` delegando el rechazo real a la API del Hostinger si no encuentra el Hash.
4. **Manejo de Renderizado (ERP)**: Se corrigió el patrón estructural del ERP para igualarlo a `cupones.php` (`renderMenuLateral($cargoOperario)`, `renderHeader(...)`), y marcado de sub-contenedores (main/sub-container).

---

## ⚙️ Configuración y Despliegue (VPS)

### Variables de Entorno (`.env` del VPS)

| Variable | Descripción |
|----------|-------------|
| `REUNIONES_API_TOKEN` | Token para que el VPS escriba en la API (`RESUMEN_TOKEN_VPS` de `auth.php`) |
| `REUNIONES_API_BASE_URL` | `https://api.batidospitaya.com/api/resumen_reuniones_ia` |
| `RESUMEN_TOKEN_ERP` | Token para verificar que una solicitud de borrado venga del ERP (`RESUMEN_TOKEN_ERP` de `auth.php`) |
| `AUDIO_DIR` | `/opt/resumen-reuniones-ia/audio` |
| `PORT` | `8888` |

### Comandos de Mantenimiento (VPS)

Estos comandos son útiles si entras por SSH al VPS (`ssh root@198.211.97.243`):

```bash
# Ver el estado y los logs de la app en vivo (crucial para debugear Gemini)
journalctl -u resumen-reuniones-ia -f

# Reiniciar el servicio (aplica los cambios del código si editas cosas localmente en el VPS)
systemctl restart resumen-reuniones-ia

# Verificar qué fragmentos de audio aún no han sido aprobados/borrados
ls -lh /opt/resumen-reuniones-ia/audio/
```

### Despliegues Automáticos (CI/CD)

Cualquier cambio hecho aquí deberá subirse mediante el script de sistema y usará `GitHub Actions` para sincronizar solo con el VPS.

```bash
.\.scripts\gitpush.ps1 "Tu mensaje descriptivo (ej: fix: mejora del prompt IA)"
```
Esto mandará los archivos a Github, y el `deploy.yml` hará rsync y un `systemctl restart`. NO necesitas entrar al VPS para desplegar cambios de código.

---

## ⚠️ Posibles Errores Futuros y sus Soluciones

- **401 Unauthorized desde el VPS a Hostinger**: Significa que `REUNIONES_API_TOKEN` cambió o no concuerda con `RESUMEN_TOKEN_VPS` en `auth.php`.
- **422 en la grabadora (UI)**: Revisa los logs de journalctl en el VPS. A veces un error de conexión entre VPS y Hostinger al crear el estado hace fallar la grabación.
- **Audios no se borran tras aprobar**: Revisa el Nginx del VPS. `client_max_body_size` debe permitir el tráfico, pero si no se borran los audios tras aprobar en el ERP, significa que el token `RESUMEN_TOKEN_ERP` del `.env` del VPS es incorrecto.
- **Gemini devuelve fallo o 500 (API Exhausted / Quota)**: Ver los logs en `journalctl`. Ocurre si el audio es obscenamente largo (mayor al límite por minuto/día de la API). Múltiples reintentos pueden arreglarlo si es por throttling. Si la key de Gemini muere por completo, recuerda que existe un endpoint en la API de Hostinger (`obtener_key_gemini.php`) que el VPS usa para hacer "rotación diaria" en la tabla `ia_proveedores_api`. Revisa esa tabla del ERP.
