# Cambios respecto de la intranet original
- Tema tecnológico (oscuro + neón), tipografía mono en títulos y menús, logo SVG nuevo.
- Fondo animado en canvas (red de nodos interactiva) + grilla en perspectiva + halos; configurable.
- Reloj en vivo, brillo en las tarjetas que sigue al mouse, íconos sugeridos de tecnología.
- Bot de Telegram (servicio `telegram-bot`) para cargar, listar y borrar enlaces.
- API: nuevo `GET /api/services` (lectura) que usa el bot.
- Claves y token movidos a `.env` (antes estaban escritos en docker-compose.yml).
- Se quitaron los archivos duplicados de la raíz (logo.png, services.yaml, settings.yaml, js-yaml.min.js).
