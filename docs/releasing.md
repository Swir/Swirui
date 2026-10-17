# Release qualification and publication

The Windows desktop beta candidate is `0.1.0b1`, with its bounded scope defined
in [beta.md](beta.md). A passing local build does not complete the full roadmap
or establish a new GitHub CI result. Do not publish a stable release until its
agreed scope and release gates are complete. The previous `0.1.0a1` is already
published and must not be reused for changed files.

The `publish-pypi.yml` workflow now qualifies pull requests, main pushes and
manual runs without publishing. A **published GitHub Release** triggers publication
only after its own metadata, Python 3.11–3.14 quality matrix, portable build and
Windows native build/full tests succeed. Native tests must actually pass; an
unavailable adapter or failed test is not waived.

Before creating a new release:

1. Resolve outstanding release blockers and merge the reviewed candidate normally.
2. Choose a new, justified version. Update `pyproject.toml`,
   `src/swirui/__init__.py`, `native/Cargo.toml` and its Cargo lock entry.
   Python and Rust prerelease spellings must normalize to the same version.
3. Update the changelog and README with verified capabilities and limitations.
4. Run qualification for that commit. Create its matching `v<version>` tag and
   GitHub Release; the release workflow rebuilds and tests that tagged checkout.

`tools/release_contract.py` verifies package/API/native version consistency.
During a release it also checks the tag. Its artifact check requires exactly a
portable wheel, Windows x64 ABI3 wheel and source archive, compares every Python
module across all three, verifies the packaged native extension and emits SHA256
digests. Git line-ending normalization keeps Linux and Windows source payloads
comparable. Twine checks distribution metadata before upload.

Publication uses the existing `pypi` environment and PyPI Trusted Publishing,
with OIDC permission only on the publish job. The trusted publisher must match
`Swir/Swirui`, workflow `publish-pypi.yml`, environment `pypi`. Its remote
configuration is not verified by local tests. No long-lived upload token is needed.
See the [PyPI Trusted Publishing guide](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
and [GitHub release events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#release).

Existing PyPI files are not silently skipped, and GitHub release assets are not
overwritten. If publication partially fails, inspect the remote files and their
hashes before recovery; do not replace or delete an existing release blindly.

The workflow definition and local validation are preparation, not proof that
GitHub has run it or that PyPI accepted a release. Record actual run URLs and
published artifact hashes after publication.
