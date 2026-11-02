# Security boundaries

Ember is a single-owner application, not a multi-tenant service. It uses an owner-chosen password with Argon2id hashing, hashed session tokens in SQLite, HttpOnly/SameSite cookies, expiry, CSRF tokens, origin checks, host validation and password-version session invalidation. HTTPS origins produce Secure cookies and HSTS. No public registration or default password exists.

The main shell and health status may be fetched without a session; catalogue/collection APIs, evidence, photos and settings require authentication. The monitor service token authorizes only the updater/readback route, not collection access, and cannot bypass the owner interval. Service access uses `Authorization: Bearer` for THIS rebuild, not the original Sites-specific header.

Provider credentials are encrypted with the generated Fernet key; this is authenticated encryption at rest, not protection from an attacker controlling both the application server and key. Sessions, database files and key files must be protected by filesystem permissions and server administration. Private photo uploads are size/pixel limited, decoded and re-encoded as JPEG, stripping original metadata. No arbitrary user URL is fetched server-side: catalogue, eBay and FX requests go to fixed provider hosts. External image URLs are loaded by the browser and expose a network request to that source; Referrer-Policy is no-referrer.

SQLite data itself is not encrypted. Protect the server disk and backups. The local app binds loopback by default; non-local binding requires an HTTPS public origin and an appropriately configured TLS reverse proxy. TLS termination itself is an operator responsibility. Do not expose port 8000 directly to the Internet. The included Compose file binds it only on loopback.

Rate limits are per observed client address; proxy-header trust is disabled. Behind a reverse proxy this can group attempts under the proxy address. Do not enable arbitrary forwarded-header trust as a workaround. No WebAuthn/MFA, managed SSO, formal penetration test or fresh dependency advisory scan is claimed for this build.

Rotate a suspected compromised owner password with setup --reset-password; existing sessions become invalid. Preserve the encryption key or encrypted provider credentials become unreadable. Disconnect and reconnect marketplace credentials after rotating them at their source. Do not report secrets in public GitHub issues. All audits here are limited engineering verification, not a guarantee of perfect security.

## Condition-aware integrations (2.1)

PriceCharting credentials use the existing encrypted server-side store. Provider response errors are sanitized; token-bearing URLs are never echoed. The guide request is read-only, fixed-host, >=2s limited and 24h cached. No subscription or trading write is exposed. Disconnect purges only licensed provider caches. Public TCGdex guides require no secret, use fixed-host validated card IDs, reject redirects/mismatched base cards, cap responses at 2MB and preserve explicit errors. Public/specialist links are not server-side arbitrary-URL fetches. Guide values are excluded from all deal recommendations. Grader-qualified certificates avoid accidentally merging different companies' physical slabs.
