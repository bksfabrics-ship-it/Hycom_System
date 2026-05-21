# TODO

- [x] Identify root cause of Django mail error (`from_email` empty string).
- [x] Update `utils/email_service.py` to pass a non-empty `from_email` (use `settings.DEFAULT_FROM_EMAIL` or `EMAIL_HOST_USER`) and add a guard.
- [ ] Set required environment variables (`EMAIL_HOST_USER` and/or `DEFAULT_FROM_EMAIL`) in your runtime.
- [ ] Restart Django server and re-trigger the email-sending flow.
- [ ] If next errors appear (SMTP auth/TLS), fix SMTP configuration accordingly.

