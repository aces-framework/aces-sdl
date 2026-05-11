# Changelog Fragments

Every PR with a user-visible change adds one Markdown fragment in this
directory. At release time, `towncrier build` collates the fragments into
[`../CHANGELOG.md`](../CHANGELOG.md) and removes the consumed files.

This avoids merge conflicts from multiple PRs editing the top of
`CHANGELOG.md`.

## Add A Fragment

Create one file named:

```text
<issue>.<type>.md
```

`<issue>` is the GitHub issue or PR number. For issue-free entries, prefix a
slug with `+`, for example `+fix-typo.fixed.md`, to suppress an issue suffix.

`<type>` must be one of:

- `security`
- `added`
- `changed`
- `deprecated`
- `removed`
- `fixed`

The file body is the bullet text. Keep it to one paragraph when possible.

## Build The Changelog

```sh
uvx towncrier build --version <X.Y.Z> --date $(date -u +%F)
```

Preview without writing:

```sh
uvx towncrier build --draft --version <X.Y.Z>
```
