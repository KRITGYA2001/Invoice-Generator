import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "invoice_generator.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.test import Client

invoice_id = "37de81e6-125a-4f93-b13c-d6b1a262a899"
user = get_user_model().objects.filter(company_profile__isnull=False).first()
client = Client(HTTP_HOST="127.0.0.1:8000")
client.force_login(user)

response = client.post(f"/invoices/{invoice_id}/send-email/", {"email": "test@example.com"})
print("STATUS", response.status_code)
print(response.content.decode("utf-8", errors="ignore"))
