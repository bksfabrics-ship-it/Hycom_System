# Invoice Converter over an SSH Port Forward

Use this when the converter runs on an office Windows PC and another computer
needs to use it in a browser. The tunnel carries the browser connection to the
application without exposing Django or the database directly to the network.

## On the office Windows PC

1. Set `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1` in the private `.env` file.
   These are the host names the browser will use at the other end of the tunnel.
2. Start the Django application using the deployment WSGI server, bound only
   to loopback:

   ```powershell
   waitress-serve --listen=127.0.0.1:8000 hycom_team_project.wsgi:application
   ```

3. Enable the Windows OpenSSH Server and make sure the PC is reachable through
   SSH from the other computer, preferably over the office network or a VPN.
   Restrict the Windows Firewall SSH rule to trusted networks. Do not configure
   router forwarding for Django port 8000 or database port 3306.

## On the other computer

Open a terminal and create the SSH tunnel, replacing the account and host with
the office PC's SSH account and address:

```text
ssh -N -L 8000:127.0.0.1:8000 windows-user@office-pc
```

Keep that terminal open. In a browser on the other computer, visit:

```text
http://127.0.0.1:8000/stock/invoice-converter/
```

Sign in with the Hycom application account that has Products permission, then
upload the `.xlsx` workbook and download the converted workbook. If local port
8000 is already in use on the other computer, change the first `8000` in the
SSH command to another free port (for example `18000`) and use that port in the
browser URL.

The converter is not anonymous: the existing login and Products permission
checks still apply. This SSH tunnel is for trusted users; do not expose the SSH
service publicly without suitable network restrictions and account security.
