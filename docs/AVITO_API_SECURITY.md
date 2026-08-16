# Avito API connection safety

This repository expects three GitHub Actions secrets:

- `AVITO_CLIENT_ID`
- `AVITO_CLIENT_SECRET`
- `AVITO_USER_ID`

The workflow `.github/workflows/avito-readonly-check.yml` performs authentication only.
It does not create, edit, publish, promote, pause, or delete Avito listings and cannot
spend advertising funds.

The probe never prints the client ID, client secret, access token, or user ID. It reports
only whether the required secrets exist, whether the user ID has a valid format, and
whether Avito returned an access token.

If a credential was ever pasted into a chat, issue, commit, log, or public file, revoke it
in Avito and replace the corresponding GitHub secret before running this check.
