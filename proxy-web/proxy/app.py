import os
import requests
import logging
from flask import Flask, redirect, url_for, session, request, Response, render_template
from authlib.integrations.flask_client import OAuth

# Configuração de Log de Auditoria
logging.basicConfig(level=logging.INFO, format='%(asctime)s - AUDIT - %(message)s')
logger = logging.getLogger(__name__)

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET")

# --- CONFIGURAÇÕES VIA AMBIENTE ---
EXT_DOMAIN = os.environ.get("EXTERNAL_DOMAIN", "localhost")
LOGIN_DOMAIN = os.environ.get("ALLOWED_LOGIN_DOMAIN", "gmail.com")
SPECIFIC_USERS = [u.strip().lower() for u in os.environ.get("ALLOWED_USERS", "").split(",") if u.strip()]

APPLICATIONS = {
    "nginx-interno": {
        "name": "Servidor Nginx",
        "url": "http://nginx-internal:8080",
        "icon": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/nginx/nginx-original.svg"
    }
}

def has_access(user_email):
    email = user_email.lower()
    return email.endswith(f"@{LOGIN_DOMAIN}") or email in SPECIFIC_USERS

# --- GOOGLE OAUTH ---
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

@app.route('/login')
def login():
    # Usa o domínio configurado no .env para o redirect_uri
    redirect_uri = f"https://{EXT_DOMAIN}/callback"
    return google.authorize_redirect(redirect_uri)

@app.route('/callback')
def auth():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    if user_info:
        session['user'] = user_info
        logger.info(f"LOGIN: {user_info['email']} no domínio {EXT_DOMAIN}")
    return redirect(url_for('dashboard'))

@app.route('/')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    if not has_access(user['email']):
        logger.warning(f"NEGADO: {user['email']}")
        return "<h1>Acesso Negado</h1>", 403
    
    return render_template('dashboard.html', apps=APPLICATIONS, user=user)

@app.route('/go/<app_id>/', defaults={'path': ''})
@app.route('/go/<app_id>/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_gateway(app_id, path):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    if not has_access(user['email']) or app_id not in APPLICATIONS:
        return "Acesso Negado", 403

    if not request.path.endswith('/') and not path:
        return redirect(request.path + '/')

    target_url = f"{APPLICATIONS[app_id]['url']}/{path}"
    logger.info(f"PROXY: {user['email']} -> {app_id}/{path}")

    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            params=request.args,
            headers={k: v for k, v in request.headers if k.lower() not in ['host', 'content-length']},
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=15
        )
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
        return Response(resp.content, resp.status_code, headers)
    except Exception as e:
        return f"Erro de conexão interna", 502
