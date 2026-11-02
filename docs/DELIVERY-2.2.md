# Ember 2.2 delivery — 2 November 2026

The complete application source is in [openGallo/poke](https://github.com/openGallo/poke), in the owner's existing public repository. Open `Ember.code-workspace` in Visual Studio Code to edit and debug it. Personal collection records, credentials and local databases are excluded from Git.

## Install the standalone Mac application

Both packages contain their own Python runtime and dependencies. Normal use does not require terminal commands or a separately installed Python.

1. In Apple menu → About This Mac, check the chip or processor.
2. Open [the successful Mac build](https://github.com/openGallo/poke/actions/runs/41482283641). Download `Ember-macos-15` for Apple Silicon or `Ember-macos-15-intel` for Intel. GitHub may ask you to sign in to download Actions artifacts.
3. Extract the artifact ZIP, then the application ZIP inside it. A directly supplied `Ember-macOS-arm64.zip` or `Ember-macOS-x86_64.zip` is already the inner ZIP and needs only one extraction.
4. Move `Ember.app` to Applications and open it. If you are replacing an older copy, quit that copy first. Choose your owner password on first launch.
5. Keep Ember open for scans and notifications. Choose English/French scope, delivery country, budget and accepted conditions in Settings; add your collection manually or by CSV.

The packages are ad-hoc signed and are not Apple-notarized. For an unverified-developer block on a package you obtained here, [Apple documents the per-app launch exception](https://support.apple.com/en-hk/102445): try opening Ember, then go to System Settings → Privacy & Security → Open Anyway for Ember and confirm Open. A damaged-file or malware alert requires investigation rather than this exception.

Both builds and their packaged local-server startup were tested on macOS 15. Native window rendering, Finder launch, notifications and download dialogs have not been visually checked on a user's Mac. Older macOS compatibility is unverified even though the bundle declares a lower minimum version.

Your database, photos and encrypted settings stay in `~/Library/Application Support/Ember`. Replacing the application does not replace those records. Settings provides a full private backup; see [backup and restore](MAC-DESKTOP.md#backup-and-restore).

## Verified packages

The application binaries were built from source commit `f11a8031da0ea0d7bf341d8bf5f969ada5b2a4e6`. Later publication changes contain documentation and evidence only. Both Mac jobs passed all 259 tests, the build and packaged HTTP/setup/asset startup checks. Downloads passed CRC, executable-mode, CPU-architecture, version and catalogue/UI presence checks.

| Application ZIP | Architecture | Bytes | SHA-256 |
| --- | --- | --- | --- |
| `Ember-macOS-arm64.zip` | Apple Silicon | 39,848,930 | `de867c98ab23d50482bedc24e861fab0cb73bb9416d3854f5ca43d2faf2d0ea9` |
| `Ember-macOS-x86_64.zip` | Intel | 41,560,445 | `a80bd6b3d77a27280b97727d70ae87e4c67651cb4386c7d9ccd4897ee3ad9851` |

GitHub Actions retains these artifacts until 16 November 2026, subject to repository retention or manual removal. They are not permanent GitHub release assets. To reproduce them, run the **Build Mac application** workflow manually, or use `Build-Mac-App.command` on the matching architecture. Lockfiles, build script and PyInstaller specification are included in the repository.

## Sources and coverage

| Source | Available behavior | Setup or limitation |
| --- | --- | --- |
| TCGdex / Cardmarket / TCGplayer aggregate guides | Free public per-card guide refresh | Exact base-card mapping must be reviewed. Aggregates can mix conditions or variants; they never establish an exact-condition bargain. |
| eBay | OAuth/Browse active listings, item checks, scan and asking-price history | Eligible production API credentials are required in Settings. Live authenticated access has not been verified. No completed-sale feed is included. |
| Cardmarket listings and specialist shops | Research links, source-linked manual records and CSV imports | No automatic Cardmarket listing crawler or continuous shop crawler is supplied. |
| PriceCharting | Optional official current-price connector | Existing licensed token and exact product mapping required; no individual historical-sale feed. |
| Frankfurter | Dated reference FX | Stale or missing rates remain unknown. |

Without eBay credentials, the collection, checklist, import/export, manual evidence, price comparison and radar remain available; an automatic scan reports its blocked status and does not fabricate listings. Only disclosed completed sales in equivalent condition buckets support exact-condition valuations. Asking prices and aggregate guides stay separate.

The dated catalogue contains 485 active entries, including 179 in the default English/French scope. Forty worldwide entries are provisional. Worldwide completeness and a distinct-artwork census are unverified. A raw NM/Mint copy is never treated as evidence of a future PSA 10 grade. Unknown delivery costs and sparse price evidence remain explicit.

See [full verification and limits](VERIFICATION-2.2.md), [development and connector instructions](../README.md#edit-in-visual-studio-code) and [source provenance](SOURCE-PROVENANCE.md).
