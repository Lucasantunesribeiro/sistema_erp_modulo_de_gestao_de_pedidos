"""
Configuração do Celery para o projeto ERP Order Management.

O módulo DJANGO_SETTINGS_MODULE é definido antes da instanciação da app,
garantindo que o Celery leia as settings do Django (prefixo CELERY_).
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("erp")

# Lê configurações do Django com prefixo CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")

# Descobre tasks.py em cada app instalada
app.autodiscover_tasks()
