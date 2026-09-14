import os
import re
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, render_template, g, redirect, url_for, abort

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "encuesta.db")

# Usuario y contraseña del panel /admin.
# En local usan estos valores por defecto; en Render los defines como
# variables de entorno ADMIN_USER y ADMIN_PASS (ver README).
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "cambia-esta-clave")

CAMPOS = ["q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9", "q10"]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def cerrar_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS respuestas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT NOT NULL,
            q1 TEXT,
            q2 TEXT,
            q3 TEXT,
            q4 TEXT,
            q5 TEXT,
            q6 TEXT,
            q7 TEXT,
            q8 TEXT,
            q9 TEXT,
            q10 TEXT
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS paginas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            titulo TEXT NOT NULL,
            subtitulo TEXT,
            contenido TEXT,
            imagen_url TEXT,
            tipo TEXT NOT NULL DEFAULT 'simple',
            texto_boton_si TEXT DEFAULT 'Confirmar',
            texto_boton_no TEXT DEFAULT 'No puedo',
            mensaje_confirmado TEXT DEFAULT 'Gracias por confirmar.',
            mensaje_declinado TEXT DEFAULT 'Quedó registrado, gracias por avisar.',
            creado_en TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS confirmaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pagina_id INTEGER NOT NULL,
            respuesta TEXT NOT NULL,
            fecha_hora TEXT NOT NULL,
            FOREIGN KEY (pagina_id) REFERENCES paginas (id)
        )
        """
    )
    db.commit()
    db.close()


def requiere_auth(f):
    @wraps(f)
    def decorada(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != ADMIN_USER or auth.password != ADMIN_PASS:
            return (
                "Acceso restringido.",
                401,
                {"WWW-Authenticate": 'Basic realm="Panel de administración"'},
            )
        return f(*args, **kwargs)

    return decorada


def generar_slug(texto):
    texto = texto.strip().lower()
    reemplazos = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n", "ü": "u",
    }
    for a, b in reemplazos.items():
        texto = texto.replace(a, b)
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return texto or "pagina"


def slug_disponible(db, slug, excluir_id=None):
    if excluir_id:
        fila = db.execute(
            "SELECT id FROM paginas WHERE slug = ? AND id != ?", (slug, excluir_id)
        ).fetchone()
    else:
        fila = db.execute("SELECT id FROM paginas WHERE slug = ?", (slug,)).fetchone()
    return fila is None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/enviar", methods=["POST"])
def enviar():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "No se recibieron datos."}), 400

    # Validación mínima: la pregunta 1 es obligatoria.
    q1 = (data.get("q1") or "").strip()
    if not q1:
        return jsonify({"ok": False, "error": "Falta la respuesta de la pregunta 1."}), 400

    valores = {}
    for campo in CAMPOS:
        v = data.get(campo, "")
        if not isinstance(v, str):
            v = str(v)
        valores[campo] = v.strip()[:2000]  # límite razonable por campo

    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    db = get_db()
    db.execute(
        """
        INSERT INTO respuestas (fecha_hora, q1, q2, q3, q4, q5, q6, q7, q8, q9, q10)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (fecha_hora, *[valores[c] for c in CAMPOS]),
    )
    db.commit()

    return jsonify({"ok": True, "fecha_hora": fecha_hora})


@app.route("/admin")
@requiere_auth
def admin():
    db = get_db()
    filas = db.execute(
        "SELECT * FROM respuestas ORDER BY id DESC"
    ).fetchall()

    total = len(filas)

    def promedio(campo, maximo):
        vals = []
        for f in filas:
            try:
                vals.append(float(f[campo]))
            except (TypeError, ValueError):
                continue
        if not vals:
            return 0
        return round(sum(vals) / len(vals) / maximo * 100, 1)

    def contar_positivas():
        positivas = {"Sí, logró sacarme una sonrisa", "Sí, aunque de manera moderada"}
        return sum(1 for f in filas if f["q1"] in positivas)

    stats = {
        "total": total,
        "calidad_pct": promedio("q2", 5),
        "recompra_pct": promedio("q6", 10),
        "sonrisas": contar_positivas(),
    }

    paginas = db.execute("SELECT * FROM paginas ORDER BY id DESC").fetchall()

    return render_template("admin.html", filas=filas, stats=stats, paginas=paginas)


# ---------- Gestión de páginas (CMS) ----------

@app.route("/admin/paginas")
@requiere_auth
def admin_paginas():
    db = get_db()
    paginas = db.execute("SELECT * FROM paginas ORDER BY id DESC").fetchall()
    return render_template("admin_paginas.html", paginas=paginas, pagina=None)


@app.route("/admin/paginas/nueva", methods=["GET"])
@requiere_auth
def admin_pagina_nueva():
    return render_template("admin_pagina_editar.html", pagina=None)


@app.route("/admin/paginas/crear", methods=["POST"])
@requiere_auth
def admin_pagina_crear():
    db = get_db()
    titulo = request.form.get("titulo", "").strip()
    if not titulo:
        abort(400, "El título es obligatorio.")

    slug = request.form.get("slug", "").strip() or generar_slug(titulo)
    slug = generar_slug(slug)
    base_slug = slug
    contador = 2
    while not slug_disponible(db, slug):
        slug = f"{base_slug}-{contador}"
        contador += 1

    db.execute(
        """
        INSERT INTO paginas
            (slug, titulo, subtitulo, contenido, imagen_url, tipo,
             texto_boton_si, texto_boton_no, mensaje_confirmado, mensaje_declinado, creado_en)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            slug,
            titulo,
            request.form.get("subtitulo", "").strip(),
            request.form.get("contenido", "").strip(),
            request.form.get("imagen_url", "").strip(),
            request.form.get("tipo", "simple"),
            request.form.get("texto_boton_si", "Confirmar").strip() or "Confirmar",
            request.form.get("texto_boton_no", "No puedo").strip() or "No puedo",
            request.form.get("mensaje_confirmado", "Gracias por confirmar.").strip(),
            request.form.get("mensaje_declinado", "Quedó registrado, gracias por avisar.").strip(),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    db.commit()
    return redirect(url_for("admin_paginas"))


@app.route("/admin/paginas/<int:pagina_id>/editar", methods=["GET"])
@requiere_auth
def admin_pagina_editar(pagina_id):
    db = get_db()
    pagina = db.execute("SELECT * FROM paginas WHERE id = ?", (pagina_id,)).fetchone()
    if pagina is None:
        abort(404)
    return render_template("admin_pagina_editar.html", pagina=pagina)


@app.route("/admin/paginas/<int:pagina_id>/actualizar", methods=["POST"])
@requiere_auth
def admin_pagina_actualizar(pagina_id):
    db = get_db()
    pagina = db.execute("SELECT * FROM paginas WHERE id = ?", (pagina_id,)).fetchone()
    if pagina is None:
        abort(404)

    titulo = request.form.get("titulo", "").strip()
    if not titulo:
        abort(400, "El título es obligatorio.")

    slug = generar_slug(request.form.get("slug", "").strip() or titulo)
    base_slug = slug
    contador = 2
    while not slug_disponible(db, slug, excluir_id=pagina_id):
        slug = f"{base_slug}-{contador}"
        contador += 1

    db.execute(
        """
        UPDATE paginas SET
            slug = ?, titulo = ?, subtitulo = ?, contenido = ?, imagen_url = ?,
            tipo = ?, texto_boton_si = ?, texto_boton_no = ?,
            mensaje_confirmado = ?, mensaje_declinado = ?
        WHERE id = ?
        """,
        (
            slug,
            titulo,
            request.form.get("subtitulo", "").strip(),
            request.form.get("contenido", "").strip(),
            request.form.get("imagen_url", "").strip(),
            request.form.get("tipo", "simple"),
            request.form.get("texto_boton_si", "Confirmar").strip() or "Confirmar",
            request.form.get("texto_boton_no", "No puedo").strip() or "No puedo",
            request.form.get("mensaje_confirmado", "Gracias por confirmar.").strip(),
            request.form.get("mensaje_declinado", "Quedó registrado, gracias por avisar.").strip(),
            pagina_id,
        ),
    )
    db.commit()
    return redirect(url_for("admin_paginas"))


@app.route("/admin/paginas/<int:pagina_id>/eliminar", methods=["POST"])
@requiere_auth
def admin_pagina_eliminar(pagina_id):
    db = get_db()
    db.execute("DELETE FROM confirmaciones WHERE pagina_id = ?", (pagina_id,))
    db.execute("DELETE FROM paginas WHERE id = ?", (pagina_id,))
    db.commit()
    return redirect(url_for("admin_paginas"))


@app.route("/p/<slug>")
def pagina_publica(slug):
    db = get_db()
    pagina = db.execute("SELECT * FROM paginas WHERE slug = ?", (slug,)).fetchone()
    if pagina is None:
        abort(404)
    return render_template("pagina.html", p=pagina)


@app.route("/api/confirmar/<int:pagina_id>", methods=["POST"])
def api_confirmar(pagina_id):
    db = get_db()
    pagina = db.execute("SELECT * FROM paginas WHERE id = ?", (pagina_id,)).fetchone()
    if pagina is None:
        return jsonify({"ok": False, "error": "Página no encontrada."}), 404

    data = request.get_json(silent=True) or {}
    respuesta = data.get("respuesta")
    if respuesta not in ("confirmado", "declinado"):
        return jsonify({"ok": False, "error": "Respuesta inválida."}), 400

    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO confirmaciones (pagina_id, respuesta, fecha_hora) VALUES (?, ?, ?)",
        (pagina_id, respuesta, fecha_hora),
    )
    db.commit()

    mensaje = pagina["mensaje_confirmado"] if respuesta == "confirmado" else pagina["mensaje_declinado"]
    return jsonify({"ok": True, "mensaje": mensaje, "fecha_hora": fecha_hora})


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
