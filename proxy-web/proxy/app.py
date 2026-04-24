import os
import requests
import logging
import re
from flask import Flask, redirect, url_for, session, request, Response, render_template
from authlib.integrations.flask_client import OAuth

# ================================
# CONFIGURAÇÃO DE LOGS
# ================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - AUDIT - %(message)s')
logger = logging.getLogger(__name__)

# ================================
# CONFIGURAÇÕES DE AMBIENTE
# ================================
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['AUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

EXT_DOMAIN = os.environ.get("EXTERNAL_DOMAIN", "localhost")
LOGIN_DOMAIN = os.environ.get("ALLOWED_LOGIN_DOMAIN", "gmail.com")
SPECIFIC_USERS = [u.strip().lower() for u in os.environ.get("ALLOWED_USERS", "").split(",") if u.strip()]

# ================================
# INSTÂNCIA DO APP E SEGURANÇA
# ================================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "troque-me-no-env")

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=1800
)

# ================================
# CONFIGURAÇÃO GOOGLE OAUTH
# ================================
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# ================================
# DICIONÁRIO DE APLICAÇÕES
# ================================
APPLICATIONS = {
    "nginx-internal": {
        "name": "Servidor Nginx",
        "url": "http://nginx-internal:8080",
        "icon": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/nginx/nginx-original.svg"
    },
    "grafana": {
        "name": "Grafana",
        "url": "http://grafana-internal:3000",
        "icon": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/grafana/grafana-original.svg"
    }
}

# ================================
# HELPER DE ACESSO
# ================================
def has_access(user_email):
    email = user_email.lower()
    return email.endswith(f"@{LOGIN_DOMAIN}") or email in SPECIFIC_USERS

# ================================
# ROTAS DE AUTENTICAÇÃO E DASHBOARD
# ================================
@app.route('/login')
def login():
    redirect_uri = f"https://{EXT_DOMAIN}/callback"
    return google.authorize_redirect(redirect_uri)

@app.route('/callback')
def callback():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    if user_info:
        session['user'] = user_info
        logger.info(f"LOGIN SUCESSO: {user_info['email']}")
    return redirect(url_for('dashboard'))

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = session['user']
    if not has_access(user['email']):
        return "Acesso Negado", 403
    return render_template('dashboard.html', apps=APPLICATIONS, user=user)

# ================================
# ENGINE DO PROXY (GATEWAY)
# ================================
@app.route('/go/<app_id>/', defaults={'path': ''})
@app.route('/go/<app_id>/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def proxy_gateway(app_id, path):
    if 'user' not in session:
        return redirect(url_for('login'))

    user = session['user']
    if not has_access(user['email']) or app_id not in APPLICATIONS:
        return "Acesso Negado", 403

    # Garante barra no final para caminhos base (evita erro de CSS relativo)
    if not request.path.endswith('/') and not path:
        return redirect(request.path + '/')

    target_config = APPLICATIONS[app_id]
    target_url = f"{target_config['url'].rstrip('/')}/{path}"
    prefix = f"/go/{app_id}"

    # Headers de encaminhamento para a aplicação interna
    proxy_headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'content-length']}
    proxy_headers.update({
        'Host': EXT_DOMAIN,
        'X-Forwarded-For': request.remote_addr,
        'X-Forwarded-Proto': 'https',
        'X-Forwarded-Host': EXT_DOMAIN,
        'X-Forwarded-Port': '443'
    })

    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            params=request.args,
            headers=proxy_headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=20
        )

        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = []

        for name, value in resp.headers.items():
            name_lower = name.lower()
            if name_lower in excluded_headers:
                continue

            # --- REESCRITA DE REDIRECIONAMENTO (LOCATION) ---
            if name_lower == 'location':
                # Se o Grafana já incluiu o prefixo (via ROOT_URL), não duplicamos
                if prefix in value:
                    pass
                # Se for um redirecionamento relativo (ex: /login)
                elif value.startswith('/'):
                    value = f"{prefix}{value}"
                # Se for um redirecionamento absoluto para o container interno
                elif target_config['url'] in value:
                    value = value.replace(target_config['url'], f"https://{EXT_DOMAIN}{prefix}")

            # --- AJUSTE DE COOKIES (PATH) ---
            if name_lower == 'set-cookie':
                # Força o cookie da aplicação a respeitar o subcaminho do proxy
                value = re.sub(r'(?i)path=/[^;]*', f'Path={prefix}/', value)

            headers.append((name, value))

        return Response(resp.content, resp.status_code, headers)

    except Exception as e:
        logger.error(f"ERRO PROXY ({app_id}): {e}")
        return "Erro interno no proxy", 502

if __name__ == '__main__':
    # No Docker, o Gunicorn gerencia isso, mas mantemos para compatibilidade
    app.run(host='0.0.0.0', port=443)
