# Third-party material

This private reconstruction uses third-party Python packages identified in requirements.lock. Their licenses remain applicable. No public license for the application has been selected on the owner's behalf.

The bundled seed contains source-linked factual catalogue metadata, not copied card rules or a mirrored database. Sources include TCGdex's cards-database and Bulbapedia card/release pages. Individual source URLs and review dates are attached to records. Source-documented means supported by those catalogue sources, not officially certified by Pokémon or PSA. See docs/SOURCE-COVERAGE.md for limitations and corrections.

Pokémon names, card designs, artwork, PSA branding and marketplace branding belong to their respective owners. Reference card images are external URLs, not bundled files. No copyrighted font files are included. The test screenshots show fallback artwork and isolated synthetic test states. This project is not endorsed by Pokémon, Nintendo, PSA, eBay or the catalogue maintainers.

Primary implementation references:
- https://github.com/tcgdex/cards-database
- https://tcgdex.dev/
- https://developer.ebay.com/api-docs/buy/static/buy-requirements.html
- https://developer.ebay.com/api-docs/buy/browse/resources/item_summary/methods/search
- https://frankfurter.dev/
- https://cli.github.com/manual/gh_repo_create
- https://fastapi.tiangolo.com/

## Recovered reference scans in the desktop edition

The 195 cached scans under `ember/static/cards/` are retained from the original Ember Site, sourced from TCGdex and Bulbapedia. Pokémon card imagery belongs to its respective rights holders. This personal collection tool does not claim ownership of that artwork or official affiliation. Exact source URLs and content hashes are listed in `ember/data/reference-assets.json`; per-printing image notes explain language, finish and stamp limitations.

The desktop shell adds pywebview and PyObjC components; packaging uses PyInstaller. Their respective distribution/license notices remain applicable when building a standalone package.
