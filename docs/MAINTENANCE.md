# Maintenance and GitHub publication

## Publish the reviewed source

The destination is **`openGallo/poke`**, explicitly selected and created by the owner. Its existing public visibility is preserved. Keep runtime configuration, databases, photographs and credentials outside Git.

Clone the canonical repository and open `Ember.code-workspace`. For later changes, create a feature branch, make the change and run the relevant tests. The application’s Mac build workflow runs after application changes reach main and can also be started manually. A source push does not deploy the original hosted Site.

The optional publication helper uses the official GitHub CLI on the owner’s computer. Authenticate outside the application with `gh auth login` and `gh auth setup-git`, then run from a clean main checkout:

```sh
python scripts/publish_github.py --publish
```

It verifies the account and exact destination, scans outgoing source/history, checks push permission and current visibility, pushes without force, and reads back the resulting commit. Existing public or private visibility is retained. If the named repository is absent, a new repository is created private by default. It refuses unrelated roots/remotes, dirty source and diverging histories. An old recovery bundle should be kept on a separate archival branch instead of force-pushing it over the canonical remote.

## Later updates

Use the canonical GitHub repository as the starting point. Run the checks in `docs/VERIFICATION-2.2.md`, and back up local runtime data before testing migrations. Preserve stable card IDs, exact condition buckets and the evidence boundaries. Never force-push over other work.

## Backups and restore

`python -m ember backup /secure/path/ember-YYYY-MM-DD.sqlite3` uses SQLite's backup API and verifies integrity, refusing an existing destination. Keep the encryption configuration separately, with restrictive permissions and an encrypted backup store. Source archives deliberately contain neither. A source ZIP cannot restore your live collection by itself.

For restore: stop the application, back up the current state, place the verified database and matching config.json in the chosen EMBER_DATA_DIR, restore owner-only permissions, and restart. Do not generate a replacement encryption key for an existing encrypted database. Password rotation uses setup --reset-password and retains the key. The legacy Sites export requires an explicit schema/variant mapping; automatic legacy migration is not implemented.

## Dependency and data updates

Review dependency advisories with a current scanner in a connected development environment, update deliberate pins, rebuild locks in an isolated environment and rerun tests. Do not interpret a pinned version as a security guarantee. Resolve catalogue discrepancies with linked documentary evidence; never bulk-mark imported records documented simply to improve completion statistics.

## Version 2.1 upgrade

Follow UPDATE-2.1.md. Preserve runtime/configuration, back up before automatic migration 002 and verify dual completion afterwards. The current update uses the same dependency locks and catalogue seed. Do not apply the Python migration to an old Sites/D1 database. Free public guides require no credentials; licensed PriceCharting tokens, when used, remain encrypted runtime data. Disconnect purges only that provider's cached estimates. All saved guide values are context, not sales.

## Restore the bundled Git history

The optional `.bundle` contains this reconstruction's local commit history; it is not a GitHub upload. To preserve it instead of initializing a new source ZIP history:

```sh
git clone /path/to/ember-charmander-2.1.0.bundle ember-charmander
cd ember-charmander
git remote rename origin recovery-bundle
python scripts/publish_github.py --publish
```

The recovery bundle retains the original history. Keep it separate from the new canonical repository history; the helper refuses an unrelated or diverging remote. Runtime data/configuration are never part of the bundle.
