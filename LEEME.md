# Intranet Tech

Versión tecnológica de la intranet: tema oscuro con neón (cian/violeta), fondo animado
(red de nodos que reacciona al mouse + grilla en perspectiva + halos de color), reloj en vivo
y un bot de Telegram para cargar enlaces desde el celular.

Se mantiene todo lo de la versión anterior: buscador ("/" enfoca, Enter abre, Esc limpia),
menú de áreas, edición desde la web con claves por área, respaldos automáticos y el mismo
formato de `config/services.yaml`.

## Puesta en marcha
> **En Portainer:** seguí `PORTAINER.md`. Lo de abajo es para `docker compose` por consola.

1. Copiá `.env.example` como `.env` y completá las claves (ver abajo).
2. Poné tus áreas y enlaces en `config/services.yaml` (el que viene es de ejemplo).
   Si después lo cambiás en GitHub, se aplica al redeploy (ver `SERVICES_SYNC` en PORTAINER.md).
3. `docker compose up -d --build`
4. Abrí `http://IP-DEL-SERVIDOR:8091`

## Apariencia (`config/settings.yaml`)
- `background: animated` → fondo tecnológico animado (recomendado).
  Con una URL o `/config/fondo.jpg` usa esa foto con los efectos encima. `none` lo apaga.
- `accent` / `accent2` → colores del tema (ej. `"#22d3ee"` y `"#a78bfa"`, o verde `"#22c55e"`).
- `show_host: true` → muestra el dominio debajo de cada tarjeta (apagado por defecto).
- El fondo se pausa solo si la pestaña no está visible y respeta "reducir movimiento" del sistema.

## Bot de Telegram
1. En Telegram hablale a **@BotFather** → `/newbot` → copiá el token en `TELEGRAM_TOKEN` del `.env`.
2. `docker compose up -d --build`
3. Mandale `/id` a tu bot y poné ese número en `TELEGRAM_ALLOWED_IDS` (varios separados por coma).
4. `docker compose up -d` de nuevo.

Uso:
- Mandá un link (o compartilo desde el navegador del celular hacia el bot) → elegís el área con
  botones. El nombre se toma del título de la página; podés cambiarlo con "✏️ Cambiar nombre".
- `Nombre | https://link | descripción` → con nombre y descripción propios.
- `#AREA https://link Nombre` → directo al área, sin botones.
- `/areas`, `/lista AREA`, `/nuevaarea NOMBRE`, `/borrar AREA | Nombre`, `/ayuda`.

El bot usa *long polling*: no necesita IP pública, dominio ni abrir puertos.
Guarda a través de la API, así que tiene la misma validación y respaldo que la web.
Solo responde a los IDs autorizados.

## Claves (`.env`)
- `ADMIN_PIN`: clave general (edita todo, crea/borra áreas; la usa el bot).
- `AREA_PINS`: clave por área, ej. `SISTEMAS=1111;DESARROLLO=2222`.
- El `.env` está en `.gitignore`: las claves ya no quedan en el repositorio.

## Mantenimiento
- Logs del bot: `docker logs intranet-tech-bot`
- Editar a mano: `docker exec -it intranet-tech-api vi /data/services.yaml`
- Respaldos: `docker exec intranet-tech-api ls /backups`
