# Paused checkpoint — 2 November 2026

**Historical checkpoint:** the owner resumed this work with “finish”. Documentation and delivery are completed in [DELIVERY-2.2.md](DELIVERY-2.2.md). The remaining text records the earlier pause state.

The owner requested a pause and asked to save progress. Resume only when asked. This checkpoint saves pending documentation and the handoff; it does not change the application or merge anything into `main`.

## Saved application

- Canonical repository: https://github.com/openGallo/poke (existing public visibility preserved).
- Published `main`: `f11a8031da0ea0d7bf341d8bf5f969ada5b2a4e6`.
- Published source tree: `92a44d621b70105ab33e10ffb59c711dc6144fbb`.
- All 307 imported source files matched the prepared checkout byte-for-byte, including executable modes.
- The latest local application suite passed 259 tests. Application code has not changed since that verification.
- Runtime databases, collection records, credentials and production photos are excluded from Git.
- Pending README, verification-document and publication-receipt updates are saved on `checkpoint/pause-2026-11-02`; they have not been merged into `main`.

## Mac builds and downloads

The [Mac workflow run](https://github.com/openGallo/poke/actions/runs/41482283641) completed successfully for both Apple Silicon (`macos-15`) and Intel (`macos-15-intel`) at the published source commit. Both jobs ran the suite, built the standalone application and passed the packaged-runtime startup check.

| Architecture | Artifact | Artifact ID | Recorded expiry (UTC) |
| --- | --- | --- | --- |
| Apple Silicon | `Ember-macos-15` | `13160977400` | 16 November 2026, 16:43 |
| Intel | `Ember-macos-15-intel` | `13160114376` | 16 November 2026, 16:35 |

These are GitHub Actions artifacts, not permanent release assets. They have not been downloaded into this checkpoint. Rebuild from the saved source if they expire.

Native window rendering, Finder launch, notification delivery and download dialogs still require a visual check on a Mac. The packages are ad-hoc signed; Developer ID signing and Apple notarization have not been performed.

## Where to resume

1. Read this checkpoint, the README, `docs/VERIFICATION-2.2.md` and `docs/SOURCE-PROVENANCE.md`; verify the current GitHub branch heads before writing.
2. Update the pending README and verification text to reflect that both Mac architectures now pass. The receipt currently records the earlier Intel result; the completed workflow above supplies the later Apple Silicon evidence.
3. Review and publish those documentation changes when resuming. The full application source is already on `main`; do not repeat the source import.
4. Download the appropriate Mac artifact and verify the native launch experience on the user's Mac. Keep all existing source-capability and price-evidence limitations explicit.

## Local recovery context

The working checkout is `/workspace/scratch/7bb4cccd06c9/ember-desktop`, with origin `https://github.com/openGallo/poke.git`. Scratch storage may expire; use the remote checkpoint branch for durable recovery.

Original local source history is retained on `archive/ember-before-poke` (`1a3ae516e36791f0c43903747ab59b3ed0433b14`) and the prepared import on `archive/ember-publication-source` (`15e6008ff3cf45cf9acf0f89ec6c2ce05bdf902e`). The previously delivered source ZIP also contains `ember-history.bundle`. See the provenance document: the imported GitHub history has new commit identities.

The authenticated GitHub connector was used for publication. This checkout has no configured GitHub CLI/token credentials for a native push. Preserve existing history and repository visibility; never force-push.
