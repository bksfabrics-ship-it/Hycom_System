# Internet Deployment (Windows, HTTPS Reverse Proxy)

This makes the full Hycom application reachable over the internet. The existing
login and module permissions remain in place; the SAP XML export separately
requires `SAP_API_KEY`. Anyone who can reach the public website can still reach
the login page, so use strong staff passwords and keep the server patched.

## 1. Prepare a domain and private settings

Point a public DNS A record (and, if used, AAAA record) at the office's public
IP address. The ISP/router must permit inbound connections; port forwarding
will not work through carrier-grade NAT without an ISP-provided public IP.

Create a private `.env` file beside `manage.py` (do not commit it) and set:

```dotenv
DJANGO_SECRET_KEY=<unique-long-random-value>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=hycom.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://hycom.example.com
DJANGO_TRUST_PROXY_SSL=True
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SECURE_COOKIES=True
DJANGO_SECURE_HSTS_SECONDS=0
SAP_API_KEY=<separate-strong-random-value>
```

Include every hostname staff will use in `DJANGO_ALLOWED_HOSTS`, and every
HTTPS origin in `DJANGO_CSRF_TRUSTED_ORIGINS`. Origins include the scheme, such
as `https://hycom.example.com`; allowed hosts do not include a scheme or port.
Generate separate random values for the Django secret and SAP API key. Keep
`DJANGO_SECURE_HSTS_SECONDS=0` until HTTPS has been verified; then consider
setting it to `31536000`.

The `DJANGO_TRUST_PROXY_SSL` option is safe only when the reverse proxy overwrites
the `X-Forwarded-Proto` header and the Django server cannot be reached directly
from untrusted networks.

## 2. Run Django behind the proxy

Install the project requirements, then run the Windows-compatible Waitress WSGI
server from the directory containing `manage.py`:

```powershell
waitress-serve --listen=127.0.0.1:8000 hycom_team_project.wsgi:application
```

The app binds to loopback, so clients must connect through the reverse proxy.
Do not use Django's `runserver` for an internet-facing deployment.

Run `python manage.py collectstatic` and configure the reverse proxy to serve
files from the resulting `staticfiles` directory for `/static/`. Forward all
other paths (including `/api/`, `/accounts/`, `/stock/`, `/returns/`, and
`/reports/`) to `http://127.0.0.1:8000`. The proxy must preserve the public
`Host` header and set `X-Forwarded-Proto` to the incoming scheme.

## 3. Configure HTTPS and forwarding

For example, a Caddy site block for an acquired domain can reverse proxy to
Waitress and automatically manage HTTPS certificates:

```caddyfile
hycom.example.com {
    handle /static/* {
        root * D:/path/to/hycom_team_project/staticfiles
        file_server
    }

    handle {
        reverse_proxy 127.0.0.1:8000
    }
}
```

Replace the domain and static directory with the real values. Caddy needs to
be reachable on ports 80 and 443 to obtain and renew certificates. Configure
the router to forward TCP ports 80 and 443 to the computer running Caddy, and
allow those ports in Windows Firewall. Do **not** forward ports 8000 or 3306;
the Django app and MySQL database should not be directly internet-accessible.

Before using the public address, verify HTTPS, staff login, static files, CSRF
protected forms, and the SAP endpoint with its bearer key. Keep database
credentials private and use a dedicated database account rather than MySQL
root for the application.
