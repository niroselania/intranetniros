# Instalar en Portainer

Usa el puerto **8091** para no chocar con la intranet actual (8090).
Los nombres de contenedores y volúmenes también son distintos: pueden convivir.

## Opción A (recomendada): desde GitHub, igual que la intranet actual
1. En GitHub creá un repositorio nuevo, por ejemplo `intranet-tech` (puede ser privado).
2. Subí el **contenido** de la carpeta `intranet-tech` (Add file > Upload files).
   No subas un archivo `.env` con claves.
3. En Portainer: **Stacks > Add stack**
   - Name: `intranet-tech`
   - Build method: **Repository**
   - Repository URL: `https://github.com/TU-USUARIO/intranet-tech`
   - Repository reference: `refs/heads/main`
   - Compose path: `docker-compose.yml`
   - Si el repo es privado: activá **Authentication** (usuario + token de GitHub).
   - Opcional: **GitOps updates** (polling 5m) para que se actualice solo cuando subas cambios.
4. **Environment variables** → "Advanced mode" (o "Load variables from .env file" y subí `.env.example`):
   ```
   PORT=8091
   ADMIN_PIN=tu-clave-larga
   AREA_PINS=
   TELEGRAM_TOKEN=
   TELEGRAM_ALLOWED_IDS=
   INTRANET_URL=http://IP-DEL-SERVIDOR:8091
   ```
5. **Deploy the stack**. Portainer construye las 3 imágenes (tarda 1–2 minutos la primera vez).
6. Abrí `http://IP-DEL-SERVIDOR:8091`.

## Activar el bot de Telegram
1. En Telegram: **@BotFather** → `/newbot` → copiá el token.
2. En Portainer: Stacks > intranet-tech > **Editor** (variables abajo) → pegá `TELEGRAM_TOKEN` →
   **Update the stack** (con "Re-pull image and redeploy" si es repositorio).
3. Mandale `/id` al bot → poné ese número en `TELEGRAM_ALLOWED_IDS` → **Update the stack** otra vez.
4. Mandale un link al bot y elegí el área.

Si algo no anda: Containers > `intranet-tech-bot` > **Logs**.

## Cambiar cosas desde GitHub
- `settings.yaml`, el logo y el código: se aplican siempre al hacer **Pull and redeploy**.
- `services.yaml` (los enlaces) depende de la variable `SERVICES_SYNC`:
  - `auto` (por defecto): si cambiaste `services.yaml` en GitHub, al redeploy se aplica el de GitHub.
    Si no lo tocaste en GitHub, se conservan los enlaces cargados desde la web o Telegram.
  - `off`: GitHub nunca pisa los enlaces (solo web / Telegram).
  - `always`: cada redeploy pisa los enlaces con el de GitHub.
  Antes de pisarlo se guarda un respaldo (`*-antes-de-github.yaml` en el volumen de respaldos).
- **Ojo:** si cargaste enlaces desde la web o Telegram y después cambiás `services.yaml` en GitHub,
  gana GitHub. Lo más simple: elegí un solo lugar para editar los enlaces.

### Cómo aplicar un cambio
1. Guardá (commit) el cambio en GitHub.
2. Portainer > Stacks > intranet-tech > **Pull and redeploy** (o esperá el GitOps automático).
   Parar el contenedor y volver a iniciarlo **no** descarga nada de GitHub.
3. Verificá en Containers > `intranet-tech-api` > **Logs**. Tiene que decir
   `services.yaml actualizado desde GitHub`.
4. Recargá la web con Ctrl+F5.

Si el log no muestra ese mensaje, Portainer reutilizó la imagen vieja sin reconstruirla:
Images > borrá `intranet-tech-api:latest` y `intranet-tech-web:latest` (marcá *Force*) y
volvé a hacer **Pull and redeploy**.

## Opción B: sin GitHub
El editor web de Portainer ("Web editor") **no puede construir imágenes** (`build:` falla
porque no tiene los archivos). Si no querés usar GitHub:
1. Copiá la carpeta `intranet-tech` al servidor (por ejemplo `/opt/intranet-tech`).
2. Por consola en esa carpeta: `docker compose build`
   (crea `intranet-tech-web`, `intranet-tech-api` e `intranet-tech-bot`).
3. En Portainer: Add stack > **Web editor** → pegá `docker-compose.yml` **borrando las líneas
   `build:` y sus `context:` / `dockerfile:`** (quedan las `image:`) → cargá las variables → Deploy.
Cada vez que cambies código hay que repetir el paso 2.

## Notas
- Funciona en un entorno Docker "standalone" (lo normal). En Docker Swarm, Portainer no construye imágenes.
- Tus enlaces viven en el volumen `intranet-tech_intranet-config`: no se pierden al actualizar el stack.
  Respaldos en `intranet-tech_intranet-backups`.
- Para pasar los sitios de la intranet vieja: copiá su `services.yaml` dentro de `config/` y subilo a GitHub.
