# Private deployment

## Current verified status

The Mac desktop source is maintained in the owner-selected repository `openGallo/poke`. GitHub source publication does not deploy the original hosted Site. Historical 2.0/2.1 deployment reports describe earlier sessions; current desktop verification is in VERIFICATION-2.2.md.

Do not point this Python server at the legacy D1 database or assume its old credentials/IDs are compatible. Do not overwrite an existing service without a backup, tested migration and explicit destination verification. Source publication is not deployment.

## Local private use (no hosting account required)

Follow README.md. `python -m ember setup` asks for a new password locally and writes private configuration. `python -m ember serve` binds only 127.0.0.1:8000. Sessions and all saved data survive restart. This is a running local application, not a public hosted URL. It stops when its process is stopped.

## Existing server / container template

Use an already authorized server with persistent storage and HTTPS. No resource creation or payment is automated. The included Dockerfile/compose.yaml were inspected but Docker was unavailable, so image build/deployment is unverified.

1. Set `EMBER_PUBLIC_URL` to an existing HTTPS origin that you control. Keep the backend loopback-bound behind its TLS reverse proxy.
2. Review costs, storage and backups before provisioning anything. Sleeping/ephemeral hosting is unsuitable for this SQLite scheduler architecture.
3. `docker compose build` builds the app as a non-root user.
4. `docker compose run --rm app python -m ember setup --public-url "$EMBER_PUBLIC_URL"` initializes the private named volume interactively. Do not send the password in chat or put it in command-line arguments.
5. `docker compose up -d` starts one process with the persistent volume. Configure the reverse proxy to preserve the intended Host header and terminate TLS. Do not use an untrusted forwarded-host override.
6. Verify `/healthz`, anonymous API rejection, owner login, CSRF enforcement, a real reload/restart with a disposable test record, and monitor readback. Remove only the explicitly disposable test record afterwards.
7. Observe a timed scheduler execution. Then unpause monitoring and connect eligible eBay production credentials to exercise a real scan.

No paid Render resources, public preview tunnels, DNS changes or external deployments were created. A connected hosting account and its approved storage/plan are still required for external deployment. Authenticated browser access to the old URL is not authorization or technical ability to deploy new server code there.

## Rollback

Keep the previous image/source revision and a consistent SQLite backup plus encryption configuration before any update. Never restore a database while the process is writing it. Stop the app, restore the paired backup/key securely, and restart the prior compatible version. Migrations 001 and 002 are tracked and non-destructive for the maintained reconstruction. Migration 002 changes the certificate index namespace and adds observation tables; restore the pre-upgrade database/config pair before rolling back to 2.0. Every future migration needs separate review and restore testing.
