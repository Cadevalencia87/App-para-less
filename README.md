# Operación: Sacar una Sonrisa — backend

Encuesta con backend en Flask + SQLite. El diseño y las preguntas del
HTML original no se tocaron; solo el script final ahora manda los
datos al servidor en vez de simularlo en el navegador.

## Archivos

- `app.py` — servidor Flask: endpoint `/api/enviar`, panel `/admin`, base de datos.
- `templates/index.html` — tu encuesta original, con el submit conectado al backend.
- `templates/admin.html` — panel de estadísticas y tabla de respuestas.
- `requirements.txt` — dependencias.
- `encuesta.db` — se crea sola la primera vez que corres la app (no se sube a git).

## 1. Correrlo en tu PC

Necesitas Python 3.9 o más nuevo instalado.

```bash
cd encuesta-app
python3 -m venv venv
source venv/bin/activate          # en Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 app.py
```

Abre `http://127.0.0.1:5000` en tu navegador — ahí ves la encuesta.
El panel está en `http://127.0.0.1:5000/admin` (usuario y contraseña abajo).

Esto solo lo ves tú en tu propia PC. Para que tu amiga entre desde su
celular sin que tu PC esté prendida, sigue el paso 2.

## 2. Subirlo gratis a Render (recomendado)

Render te da una URL fija, funcionando aunque tu PC esté apagada.

1. Crea una cuenta gratis en https://render.com (puedes entrar con GitHub).
2. Sube esta carpeta a un repositorio de GitHub (puede ser privado).
3. En Render, clic en "New" → "Web Service" → conecta tu repositorio.
4. Configura:
   - **Runtime**: Python 3
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `gunicorn app:app`
5. En la sección "Environment", agrega dos variables:
   - `ADMIN_USER` = el usuario que quieras para el panel
   - `ADMIN_PASS` = una contraseña que solo tú conozcas
6. Clic en "Create Web Service". En unos minutos te da un link como
   `https://tu-encuesta.onrender.com` — ese se lo mandas a tu amiga.

Nota: el plan gratis de Render "duerme" el servicio tras ~15 minutos
sin uso. La primera vez que alguien entra después de eso, tarda unos
20-30 segundos en despertar — normal, no es un error.

**Importante sobre la base de datos en Render:** el plan gratis no
guarda archivos de forma permanente entre reinicios del servicio, así
que `encuesta.db` puede resetearse cuando Render reinicia el
contenedor (tras dormir, o en cada despliegue nuevo). Para esta
encuesta ficticia de una sola amiga esto normalmente no es problema
porque el servicio no se reinicia mientras está despierto. Si más
adelante quieres que los datos sean 100% permanentes pase lo que
pase, se puede agregar un "disco persistente" gratuito de Render
(Render Disks, incluido en el plan free con límite pequeño) — dímelo
y te dejo esa parte también configurada.

## 3. Panel de administración

- URL: `/admin` (por ejemplo `https://tu-encuesta.onrender.com/admin`)
- Pide usuario y contraseña (autenticación HTTP básica) — solo tú los
  conoces porque los defines como variables de entorno.
- Muestra: total de evaluaciones, % de satisfacción promedio (basado
  en la pregunta 2), % de probabilidad de recompra (pregunta 6),
  sonrisas detectadas (respuestas positivas a la pregunta 1), y la
  tabla completa con fecha/hora y todas las respuestas.

## 4. Seguridad — qué se hizo y por qué alcanza para este proyecto

- El panel `/admin` exige usuario y contraseña (HTTP Basic Auth) antes
  de mostrar cualquier dato. Sin la contraseña correcta, nadie ve las
  respuestas.
- El endpoint `/api/enviar` valida que venga la pregunta 1 antes de
  guardar nada, y recorta cada campo a 2000 caracteres para evitar que
  alguien mande texto gigante o intente saturar la base de datos.
- Se usan consultas parametrizadas en SQLite (nunca se arma SQL a mano
  con los datos del usuario), lo que evita inyección SQL.
- No es un sistema para manejar datos sensibles reales ni tráfico
  masivo — pero para que una sola persona conteste una encuesta de
  broma, es más que suficiente.

Cambia `ADMIN_PASS` por algo que no sea el valor de ejemplo antes de
subirlo — con eso ya queda razonablemente protegido.
