# Mac desktop operation

The native window uses pywebview's Cocoa/WebKit implementation. The same authenticated FastAPI application runs on a pre-bound, randomly selected `127.0.0.1` port; it is not published to a network interface. No JavaScript-to-Python control bridge is exposed. Host checks, owner authentication, CSRF, encrypted provider credentials and persistent SQLite remain in force.

First launch creates fresh private configuration only when there is no existing database/configuration. The GUI chooses the real owner password. Setup cannot be repeated over a configured installation. Existing databases without their encryption configuration are rejected rather than orphaning their credentials.

## Daily use

1. Open Ember.app and sign in. Choose languages, delivery country, budget and monitoring preferences.
2. Open the binder and record exact copies, or import a validated CSV. Settings offers the export headers/templates.
3. Connect supported sources or add actual direct listing/sale links. Review exact cards, condition and delivered costs before relying on a recommendation.
4. Save priority cards and targets in the watchlist. Saved binder searches do not change the global collection scope.
5. Leave Ember open for scheduled scans. macOS sleep and closing the app stop scanning. No launch agent or cloud schedule is installed by this desktop edition.

The source launcher first installs its pinned dependencies using an installed Python 3.12+. Its environment and logs are in Application Support/Ember. The bundled standalone build packages its own runtime. The build must run on the target Mac architecture; the Linux build environment cannot validate that executable.

## Backup and restore

Settings → Download full private backup creates a consistent ZIP with `ember.sqlite3`, `config.json` and a backup information file. SQLite's online backup API includes photographs and WAL-committed records. The matching configuration includes the key needed to read encrypted provider settings. Keep the ZIP private.

To restore, quit Ember, retain a separate copy of the current Application Support/Ember folder, then place the backup's database and matching configuration into that folder. Keep them paired. Reopen Ember and use the backed-up owner password. Do not copy SQLite `-wal`/`-shm` files from another running installation. This release provides the backup download and documented manual restore, not an automatic overwrite/restore button.

## Catalogue reconciliation

The original 476-row catalogue is reconciled with the 121-row Python reconstruction. Existing IDs are preserved. All 476 legacy entries have distinct active alias targets. Names differing only by set aliases and equivalent edition spelling are matched explicitly. Duplicated unresolved placeholders are retired only where no user reference depends on them. Already documented user records are not automatically downgraded.

The original snapshot leaves the EB Games foil unresolved. On a fresh install, its older ID remains, marked provisional for physical review; an existing owner's documented record is retained. Classic `cll` and older `clc` references share one identity per language. Case differences in source set IDs do not create extra base-card placeholders.

`ember/data/catalogue-2.1.json` retains the original 121 records. `catalogue.json` includes the stable alias map and the current seed version. Reference-image filenames are local assets; source URLs and SHA-256 hashes remain in `reference-assets.json`. Cached scans are reference material, never ownership or grading evidence.

## Build and edit

Open Ember.code-workspace to modify source. The bootstrap installs dependencies once per Python version/lockfile. `Build-Mac-App.command` packages the data, migration SQL, interface and dependencies. The standalone application remains unsigned by a Developer ID and is not notarized; ad-hoc signing is recorded accurately.

The GitHub Actions workflow targets Apple Silicon (`macos-15`) and Intel (`macos-15-intel`). It runs tests, builds the application and smoke-tests the bundled local server in isolated temporary storage before retaining its ZIP. It starts after application changes are pushed to main and also supports manual runs. Consult the actual workflow run for build and runtime results; the local Linux checks do not verify Cocoa/WebKit.
