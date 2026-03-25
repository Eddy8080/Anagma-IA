import os
from pathlib import Path
import environ

# Inicializa as variáveis de ambiente
env = environ.Env(
    DEBUG=(bool, False)
)
BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(os.path.join(BASE_DIR.parent, '.env'))

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Apps locais
    'core',
    'chat_ai',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'AnagmaCore.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'AnagmaCore.wsgi.application'

DATABASES = {
    'default': env.db()
}
# Garante que o SQLite use sempre um caminho absoluto dentro de src/
# (evita ambiguidade com o db.sqlite3 na raiz do projeto)
_db = DATABASES['default']
if _db['ENGINE'] == 'django.db.backends.sqlite3' and not os.path.isabs(_db['NAME']):
    _db['NAME'] = os.path.join(BASE_DIR, _db['NAME'])

AUTH_USER_MODEL = 'core.CustomUser'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Configurações de Sessão e Autenticação
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # Padrão: fecha ao fechar navegador
SESSION_COOKIE_AGE = 2592000            # 30 dias (em segundos)
LOGIN_REDIRECT_URL = '/chat/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR.parent, 'assets', 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Configurações de E-mail (Para teste de recuperação de senha)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Caminho do modelo safetensors (mantido como fallback)
MICROSOFT_MODEL_PATH = os.path.join(BASE_DIR.parent, 'assets', 'models', 'phi-3-mini')

# Caminho do modelo GGUF quantizado (Q4_K_M) — principal, para uso com llama-cpp-python
GGUF_MODEL_PATH = os.path.join(BASE_DIR.parent, 'assets', 'models', 'phi-3-mini-gguf', 'Phi-3-mini-4k-instruct-q4.gguf')
