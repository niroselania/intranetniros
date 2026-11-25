"""
Bot de Telegram para cargar enlaces en la intranet.

Mandale un link al bot y te pregunta en qué área guardarlo (botones).
Usa la API de la intranet (misma validación y respaldos que la web).
Sin dependencias: solo la biblioteca estándar de Python.

Variables de entorno:
  TELEGRAM_TOKEN         token que da @BotFather (obligatorio)
  TELEGRAM_ALLOWED_IDS   IDs de Telegram autorizados, separados por coma (obligatorio)
  API_URL                dirección de la API (por defecto http://intranet-api:8000)
  API_PIN                clave general de la intranet (ADMIN_PIN)
  INTRANET_URL           dirección pública de la intranet, para el botón "Abrir" (opcional)
  DEFAULT_ICON           ícono para los enlaces nuevos (por defecto 🔗)
"""
import html
import json
import os
import re
import secrets
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
ALLOWED = {int(x) for x in re.split(r"[,\s;]+", os.environ.get("TELEGRAM_ALLOWED_IDS", "")) if x.strip().lstrip("-").isdigit()}
API_URL = os.environ.get("API_URL", "http://intranet-api:8000").rstrip("/")
API_PIN = os.environ.get("API_PIN", "")
INTRANET_URL = os.environ.get("INTRANET_URL", "").strip()
DEFAULT_ICON = os.environ.get("DEFAULT_ICON", "🔗")

TG = f"https://api.telegram.org/bot{TOKEN}/"
URL_RE = re.compile(r"https?://[^\s<>\"]+", re.I)
PENDING = {}          # id corto -> {url, name, desc, user, ts}
PENDING_TTL = 3600    # los botones vencen a la hora
WAITING_NAME = {}     # chat_id -> id pendiente cuyo nombre se está cambiando

HELP = (
    "🤖 *Bot de la intranet*\n\n"
    "• Mandame un *link* y elegí el área con los botones.\n"
    "• Con nombre y descripción: `Nombre | https://link | descripción`\n"
    "• Directo a un área: `#AREA https://link` (ej. `#IA https://copilot.microsoft.com`)\n\n"
    "*Comandos*\n"
    "/areas – ver las áreas\n"
    "/lista AREA – ver los enlaces de un área\n"
    "/nuevaarea NOMBRE – crear un área\n"
    "/borrar AREA | Nombre – borrar un enlace\n"
    "/id – ver tu ID de Telegram"
)


def log(*a):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), *a, flush=True)


# ---------- Telegram ----------
def tg(method, **params):
    data = json.dumps(params).encode()
    req = urllib.request.Request(TG + method, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=65) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        log("Telegram", method, e.code, body)
        return {"ok": False}


def send(chat, text, **kw):
    return tg("sendMessage", chat_id=chat, text=text, parse_mode="Markdown",
              disable_web_page_preview=True, **kw)


def md(s):
    """Escapa texto para Markdown simple de Telegram."""
    return re.sub(r"([_*`\[])", r"\\\1", str(s))


# ---------- API de la intranet ----------
def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API_URL + path, data=data, method=method,
                                 headers={"Content-Type": "application/json", "X-Real-IP": "telegram-bot"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except ValueError:
            return {"ok": False, "error": f"Error {e.code}"}
    except OSError as e:
        return {"ok": False, "error": f"No se pudo conectar con la intranet ({e})"}


def get_data():
    r = api("GET", "/api/services")
    return r.get("data") or [] if r.get("ok") else []


def areas():
    return [next(iter(g)) for g in get_data() if isinstance(g, dict) and g]


def find_area(name):
    want = name.strip().upper()
    for a in areas():
        if a.upper() == want:
            return a
    # tolera acentos: "DOCUMENTACION" -> "DOCUMENTACIÓN"
    strip = lambda s: re.sub(r"[\u0300-\u036f]", "", unicodedata.normalize("NFD", s)).upper()
    for a in areas():
        if strip(a) == strip(want):
            return a
    return None


def add_site(area, name, url, desc=""):
    return api("POST", "/api/sites", {"area": area, "name": name[:60], "href": url,
                                       "description": desc[:160], "icon": DEFAULT_ICON,
                                       "target": "_blank", "pin": API_PIN})


# ---------- utilidades ----------
def page_title(url):
    """Intenta leer el <title> de la página para usarlo como nombre."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (intranet-bot)"})
        with urllib.request.urlopen(req, timeout=6) as r:
            if "html" not in (r.headers.get("Content-Type") or ""):
                raise ValueError
            raw = r.read(200_000).decode(r.headers.get_content_charset() or "utf-8", errors="replace")
        m = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
        if m:
            t = re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()
            if t:
                return t[:60]
    except Exception:  # noqa: página caída, sin título, etc.
        pass
    host = urllib.parse.urlparse(url).hostname or url
    return host.removeprefix("www.")[:60]


def extract_url(msg):
    """Primer link del mensaje: texto plano o link escondido en una palabra."""
    text = msg.get("text") or msg.get("caption") or ""
    for ent in (msg.get("entities") or msg.get("caption_entities") or []):
        if ent.get("type") == "text_link":
            return ent["url"]
    m = URL_RE.search(text)
    return m.group(0).rstrip(".,);]") if m else None


def cleanup():
    now = time.time()
    for k in [k for k, v in PENDING.items() if now - v["ts"] > PENDING_TTL]:
        PENDING.pop(k, None)


def area_keyboard(pid):
    names = areas()
    rows, row = [], []
    for i, a in enumerate(names):
        row.append({"text": a, "callback_data": f"s:{pid}:{i}"})
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([{"text": "✏️ Cambiar nombre", "callback_data": f"n:{pid}"},
                 {"text": "✖️ Cancelar", "callback_data": f"x:{pid}"}])
    return {"inline_keyboard": rows}


def done_markup():
    if INTRANET_URL.startswith(("http://", "https://")):
        return {"inline_keyboard": [[{"text": "🌐 Abrir intranet", "url": INTRANET_URL}]]}
    return None


# ---------- manejo de mensajes ----------
def on_message(msg):
    chat = msg["chat"]["id"]
    user = (msg.get("from") or {}).get("id")
    text = (msg.get("text") or msg.get("caption") or "").strip()

    if text.startswith("/id"):
        return send(chat, f"Tu ID de Telegram es `{user}`")
    if user not in ALLOWED:
        log("Usuario no autorizado:", user)
        return send(chat, f"⛔ No estás autorizado. Pedile al administrador que agregue tu ID `{user}` en TELEGRAM_ALLOWED_IDS.")

    # respuesta a "Cambiar nombre"
    if chat in WAITING_NAME and text and not text.startswith("/"):
        pid = WAITING_NAME.pop(chat)
        p = PENDING.get(pid)
        if not p:
            return send(chat, "Ese enlace venció. Mandalo de nuevo.")
        p["name"] = text[:60]
        return send(chat, f"Nombre: *{md(p['name'])}*\n¿En qué área lo guardo?", reply_markup=area_keyboard(pid))

    cmd, _, arg = text.partition(" ")
    cmd = cmd.split("@")[0].lower()
    arg = arg.strip()

    if cmd in ("/start", "/ayuda", "/help"):
        return send(chat, HELP)
    if cmd == "/areas":
        names = areas()
        return send(chat, "📂 *Áreas*\n" + "\n".join(f"• {md(a)}" for a in names) if names else "No hay áreas todavía. Creá una con /nuevaarea NOMBRE")
    if cmd == "/lista":
        area = find_area(arg) if arg else None
        if not area:
            return send(chat, "Usá: `/lista AREA`\nÁreas: " + ", ".join(md(a) for a in areas()))
        for g in get_data():
            if area in g:
                items = g[area] or []
                lines = [f"• [{md(next(iter(i)))}]({i[next(iter(i))].get('href', '')})" for i in items if isinstance(i, dict) and i]
                return send(chat, f"📂 *{md(area)}* ({len(lines)})\n" + ("\n".join(lines) or "Vacía"))
    if cmd == "/nuevaarea":
        if not arg:
            return send(chat, "Usá: `/nuevaarea NOMBRE`")
        r = api("POST", "/api/areas", {"name": arg, "pin": API_PIN})
        return send(chat, f"✅ Área *{md(arg.upper())}* creada" if r.get("ok") else "❌ " + md(r.get("error", "Error")))
    if cmd == "/borrar":
        area_txt, _, name = arg.partition("|")
        area, name = find_area(area_txt), name.strip()
        if not area or not name:
            return send(chat, "Usá: `/borrar AREA | Nombre del enlace`")
        for g in get_data():
            if area in g:
                for idx, i in enumerate(g[area] or []):
                    if isinstance(i, dict) and next(iter(i), None) == name:
                        r = api("DELETE", "/api/sites", {"area": area, "index": idx, "original": name, "pin": API_PIN})
                        return send(chat, f"🗑️ Borrado *{md(name)}* de {md(area)}" if r.get("ok") else "❌ " + md(r.get("error", "Error")))
        return send(chat, f"No encontré *{md(name)}* en {md(area)}")
    if cmd.startswith("/"):
        return send(chat, "No conozco ese comando. /ayuda")

    url = extract_url(msg)
    if not url:
        return send(chat, "Mandame un link (https://…). /ayuda para ver opciones.")

    # "#AREA link [nombre]" -> guarda directo
    m = re.match(r"#(\S+)\s+", text)
    # "Nombre | link | descripción"
    parts = [p.strip() for p in text.split("|")]
    name = desc = ""
    if len(parts) >= 2:
        name = parts[0] if not URL_RE.match(parts[0]) else ""
        desc = parts[2] if len(parts) >= 3 else ""
    if not name:
        rest = URL_RE.sub("", text[m.end():] if m else "").strip()
        name = rest if rest and len(parts) < 2 else page_title(url)

    if m:
        area = find_area(m.group(1))
        if not area:
            return send(chat, f"No existe el área *{md(m.group(1))}*. Áreas: " + ", ".join(md(a) for a in areas()))
        r = add_site(area, name, url, desc)
        return send(chat, f"✅ *{md(name)}* guardado en *{md(area)}*" if r.get("ok") else "❌ " + md(r.get("error", "Error")),
                    reply_markup=done_markup() if r.get("ok") else None)

    if not areas():
        return send(chat, "No hay áreas todavía. Creá una con /nuevaarea NOMBRE")
    cleanup()
    pid = secrets.token_urlsafe(6)
    PENDING[pid] = {"url": url, "name": name, "desc": desc, "user": user, "ts": time.time()}
    send(chat, f"🔗 *{md(name)}*\n{md(url)}\n\n¿En qué área lo guardo?", reply_markup=area_keyboard(pid))


def on_callback(cb):
    user = (cb.get("from") or {}).get("id")
    msg = cb.get("message") or {}
    chat, mid = msg.get("chat", {}).get("id"), msg.get("message_id")
    kind, _, rest = (cb.get("data") or "").partition(":")
    pid, _, idx = rest.partition(":")
    p = PENDING.get(pid)

    def answer(t=""):
        tg("answerCallbackQuery", callback_query_id=cb["id"], text=t)

    if user not in ALLOWED:
        return answer("No autorizado")
    if not p:
        answer("Venció")
        return tg("editMessageText", chat_id=chat, message_id=mid, text="⌛ Este enlace venció. Mandalo de nuevo.")
    if kind == "x":
        PENDING.pop(pid, None)
        answer("Cancelado")
        return tg("editMessageText", chat_id=chat, message_id=mid, text="✖️ Cancelado")
    if kind == "n":
        WAITING_NAME[chat] = pid
        answer()
        return send(chat, "Escribí el nombre que querés para el enlace:", reply_markup={"force_reply": True})
    if kind == "s":
        names = areas()
        if not idx.isdigit() or int(idx) >= len(names):
            return answer("Las áreas cambiaron, mandá el link de nuevo")
        area = names[int(idx)]
        r = add_site(area, p["name"], p["url"], p["desc"])
        if r.get("ok"):
            PENDING.pop(pid, None)
            answer("Guardado")
            kw = {"reply_markup": done_markup()} if done_markup() else {}
            return tg("editMessageText", chat_id=chat, message_id=mid, parse_mode="Markdown",
                      text=f"✅ *{md(p['name'])}* guardado en *{md(area)}*", **kw)
        answer()
        return send(chat, "❌ " + md(r.get("error", "Error")))
    answer()


def main():
    if not TOKEN:
        log("Falta TELEGRAM_TOKEN: el bot no arranca.")
        while True:
            time.sleep(3600)
    if not ALLOWED:
        log("ATENCIÓN: TELEGRAM_ALLOWED_IDS está vacío. Nadie puede cargar enlaces; usá /id para ver tu ID.")
    me = tg("getMe")
    log("Bot iniciado:", (me.get("result") or {}).get("username"), "| usuarios autorizados:", len(ALLOWED))
    tg("setMyCommands", commands=[
        {"command": "ayuda", "description": "Cómo usar el bot"},
        {"command": "areas", "description": "Ver áreas"},
        {"command": "lista", "description": "Enlaces de un área"},
        {"command": "nuevaarea", "description": "Crear un área"},
        {"command": "borrar", "description": "Borrar un enlace"},
        {"command": "id", "description": "Ver mi ID de Telegram"},
    ])
    offset = 0
    while True:
        r = tg("getUpdates", offset=offset, timeout=50, allowed_updates=["message", "callback_query"])
        if not r.get("ok"):
            time.sleep(5)
            continue
        for u in r.get("result", []):
            offset = u["update_id"] + 1
            try:
                if "message" in u:
                    on_message(u["message"])
                elif "callback_query" in u:
                    on_callback(u["callback_query"])
            except Exception as e:  # noqa: un mensaje raro no debe tirar el bot
                log("Error procesando update:", repr(e))


if __name__ == "__main__":
    main()
