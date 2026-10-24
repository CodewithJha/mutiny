# Bundled UI fonts

The UI loads Latin Rubik (variable, weights 400–800) and IBM Plex Mono
(weights 400, 500, 600) through `next/font/local`. Builds do not fetch Google
Fonts CSS or font files.

Unmodified WOFF2 files were extracted from these npm packages, with the archive
SHA-512 checked against the registry's `dist.integrity`:

- `@fontsource-variable/rubik@5.3.0`: `files/rubik-latin-wght-normal.woff2`
- `@fontsource/ibm-plex-mono@5.3.0`: `files/ibm-plex-mono-latin-{400,500,600}-normal.woff2`

Both fonts use the SIL Open Font License 1.1. Their copyright notices and
licenses are included beside the font files. Preserve these when updating fonts.
