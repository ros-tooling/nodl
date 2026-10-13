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
python3 -m unittest discover -s tools/tests -q
python3 tools/check_release_versions.py .
```

Add new package manifests and Python setup files to `extra-files` in `release-please-config.json`.
Keep `x-release-please-version` on each Python version line; XML versions update directly.
CI rejects version drift and missing update coverage.

## Future Bloom releases

The workflow contains a fully commented, **untested** Jazzy example.
It needs `BLOOM_RELEASE_PAT` (classic `public_repo` + `workflow` scopes) and variable `BLOOM_GITHUB_USER` (the PAT owner's login).
The owner needs push access to `ros2-gbp/nodl-release` and permission to create/update a `ros/rosdistro` fork and open an upstream PR.
Authorize organization SSO if required; `GITHUB_TOKEN` cannot provide this cross-repository access.
The tokens may share a PAT if its owner has all required access; separate secrets allow independent ownership and rotation.

Before enabling Bloom, validate:

- The Jazzy track imports the intended unprefixed tag (`release-tag: :{version}`), not a newer version from `main`.
- Included/ignored packages, rosdep dependencies, and target distro packaging.
- Package `CHANGELOG.rst` files; release-please updates only the root Markdown changelog.
- A pinned Bloom toolchain, tested interactively by the maintainer.
  New distro tracks need separate setup; serialize releases to the shared release repo.

Release-please owns version bumps and tags; do not also run `catkin_prepare_release`.
Bloom packages an existing source release and opens a rosdistro PR.

References: [release-please configuration](https://github.com/googleapis/release-please/blob/main/docs/customizing.md), [CI token behavior](https://github.com/googleapis/release-please-action#other-actions-on-release-please-prs), [ROS tracks](https://docs.ros.org/en/rolling/How-To-Guides/Releasing/Release-Track.html), [Bloom PAT scopes](https://github.com/ros-infrastructure/bloom/blob/master/bloom/github.py).
