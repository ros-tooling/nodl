# Releases

All packages, including tests and tutorials, share one version.
The manifest starts at `2.0.3`; `bootstrap-sha` pins the initial history scan to that tag, which has no GitHub Release.
Release-please ignores this boundary after its first release.

## Tag releases

1. Squash merge conventional PRs: `fix:` bumps patch, `feat:` bumps minor, and `!` or a `BREAKING CHANGE:` footer bumps major.
2. Release-please opens or updates a PR with package versions and root `CHANGELOG.md` entries.
3. Review the changes and CI, then merge to create an unprefixed tag such as `2.1.0` and a GitHub Release.

Enable **Allow GitHub Actions to create and approve pull requests** in repository Actions settings.
No package publishing or automatic merging is enabled.
Manual workflow dispatch runs version checks only.

### Optional CI token

By default, release-please uses `GITHUB_TOKEN`; its generated PRs and tags do not trigger CI.
A maintainer can close and reopen the release PR manually to trigger CI before merging.
For automatic CI, add Actions secret `RELEASE_PLEASE_TOKEN` and uncomment the workflow's `token:` line.
The PAT owner needs repository write access.
Use fine-grained Contents, Issues, and Pull requests write permissions, or classic `public_repo` scope.
Authorize organization SSO if required.

### Version checks

```bash
python3 -m unittest discover -s tools/tests -p 'test_release_versions.py' -q
python3 tools/check_release_versions.py .
```

Add new package manifests to `extra-files` in `release-please-config.json`.
Python setup files read the version from their adjacent `package.xml`; no duplicate version needs updating.
CI checks manifest versions, update coverage, and Python version loading.
