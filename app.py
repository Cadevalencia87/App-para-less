import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, render_template, g

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

    return render_template("admin.html", filas=filas, stats=stats)


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
