#!/bin/bash
set -e

# Set Django settings module
export DJANGO_SETTINGS_MODULE=backend.settings

# Usual Django setup
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Create Django admin user if it doesn't exist
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='engrjoelivon').exists():
    User.objects.create_superuser('engrjoelivon', 'Nawoitomo@1985')
    print('Admin user created successfully')
else:
    print('Admin user already exists')
"

# Start the application
exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 --log-level info backend.wsgi:application
133.23 --project=esaasolution
When adding a new IP address to authorized networks, make sure to also include any IP addresses that have already been authorized. Otherwise, they will be 
overwritten and de-authorized.

Do you want to continue (Y/n)?  y

The following message will be used for the patch API method.
{"name": "engrjoelivon", "project": "esaasolution", "settings": {"ipConfiguration": {"authorizedNetworks": [{"value": "147.194.133.23"}]}}}
Patching Cloud SQL instance...done.                                                                                                                                
Updated [https://sqladmin.googleapis.com/sql/v1beta4/projects/esaasolution/instances/engrjoelivon].