# Publishing replayio to PyPI

This is a step-by-step checklist for shipping `replayio` v1.0.0 (and future
versions). It assumes the project layout already in this repo (`src/replayio/`,
`pyproject.toml`, `README.md`, `LICENSE`).

## 0. One-time setup

1. **Create accounts**
   - [PyPI](https://pypi.org/account/register/) (production releases)
   - [TestPyPI](https://test.pypi.org/account/register/) (dry runs — strongly recommended
     before your first real publish)
2. **Enable 2FA** on both accounts (PyPI requires it for publishing).
3. **Create API tokens** instead of using your password:
   - PyPI → Account Settings → API tokens → "Add API token"
   - Scope it to the `replayio` project (you can only do this *after* the project
     exists — for the very first upload, scope it to "entire account", then narrow it
     afterward).
   - Do the same on TestPyPI.
4. **Store credentials** in `~/.pypirc` (or use environment variables / a secrets
   manager in CI — never commit tokens):

   ```ini
   [distutils]
   index-servers =
       pypi
       testpypi

   [pypi]
   username = __token__
   password = pypi-AAAA...   # your PyPI API token

   [testpypi]
   repository = https://test.pypi.org/legacy/
   username = __token__
   password = pypi-BBBB...   # your TestPyPI API token
   ```

5. **Install the build/upload tooling** (once, in a venv):

   ```bash
   python -m pip install --upgrade build twine
   ```

## 1. Pre-flight checklist

Before every release:

- [ ] Version bumped in **two places** (keep them in sync):
  - `pyproject.toml` → `[project] version = "X.Y.Z"`
  - `src/replayio/_version.py` → `__version__ = "X.Y.Z"`
- [ ] `README.md` reflects any new features / breaking changes
- [ ] `CHANGELOG` entry added (see §5)
- [ ] Tests pass: `pytest`
- [ ] Manual smoke test passes: `python scripts/manual_test.py`
- [ ] Load test still shows zero event loss: `python scripts/load_test.py`
- [ ] `LICENSE` and `pyproject.toml` author/URL fields point to *your* repo, not a
      placeholder
- [ ] No secrets, `.env` files, or local `.replayio/` session data included in the
      package (check with the `tar tf` step in §3)

## 2. Choose and reserve your package name

Verify the name is available:

```bash
pip index versions replayio   # or just check https://pypi.org/project/replayio/
```

If `replayio` is taken, fall back to one of the alternatives already scoped for this
project (`replayio`, `backend-replay`, `replay-engine`, `pyreplay`, `reqreplay`) and
update the `name` field in `pyproject.toml` accordingly. The **import name**
(`import replayio`) can stay the same even if the **distribution name** on PyPI
differs, but for a v1.0 launch it's much less confusing to keep them identical.

## 3. Build the distribution

From the project root (where `pyproject.toml` lives):

```bash
rm -rf dist/ build/ src/*.egg-info
python -m build
```

This produces:

```
dist/
  replayio-1.0.0-py3-none-any.whl
  replayio-1.0.0.tar.gz
```

Sanity-check the contents before uploading anything:

```bash
tar tzf dist/replayio-1.0.0.tar.gz | sort
python -m zipfile -l dist/replayio-0.1.0-py3-none-any.whl
```

You're looking for: `src/replayio/**/*.py`, `LICENSE`, `README.md`, `py.typed`, and
`pyproject.toml` — and nothing else (no `.replayio/` session folders, no `__pycache__`,
no test fixtures).

Then run twine's own validator:

```bash
python -m twine check dist/*
```

## 4. Test on TestPyPI first

**Always do this before a real release**, especially your first one.

```bash
python -m twine upload --repository testpypi dist/*
```

Then install it into a clean virtual environment to confirm it actually works from
the outside:

```bash
python -m venv /tmp/replayio-test-env
source /tmp/replayio-test-env/bin/activate
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            replayio

python -c "import replayio; print(replayio.__version__)"
python -c "from replayio import Recorder, Replayer, JSONLStorage; print('ok')"
replayio --help
deactivate
```

(`--extra-index-url` is needed because TestPyPI doesn't mirror `requests` and other
real dependencies — it only hosts your test upload.)

## 5. Tag the release in git

```bash
git add pyproject.toml src/replayio/_version.py README.md
git commit -m "Release v1.0.0"
git tag -a v1.0.0 -m "replayio v1.0.0"
git push origin main --tags
```

If you keep a `CHANGELOG.md`, add an entry like:

```markdown
## [1.0.0] - 2026-07-22
### Added
- Initial release: Recorder, Replayer, Comparator
- requests / httpx / SQLAlchemy adapters
- JSONL and SQLite storage backends
- HTML and JSON reporting
- CLI: sessions, replay, export, config
```

## 6. Publish to the real PyPI

Once TestPyPI installation works cleanly:

```bash
python -m twine upload dist/*
```

Verify:

```bash
pip install replayio
python -c "import replayio; print(replayio.__version__)"
```

And check the live listing at `https://pypi.org/project/replayio/` — this is exactly
what renders your `README.md`, so review it there too.

## 7. Automating this with GitHub Actions (optional but recommended)

Once you're comfortable with the manual flow, wire up trusted publishing (no stored
API tokens needed) via PyPI's [OIDC-based "Trusted Publisher"](https://docs.pypi.org/trusted-publishers/)
support:

1. On PyPI: Project → Publishing → "Add a new publisher" → GitHub → fill in your repo,
   workflow filename (e.g. `.github/workflows/publish.yml`), and environment name
   (e.g. `release`).
2. Add a workflow that builds on tag push and uploads via
   `pypa/gh-action-pypi-publish`:

   ```yaml
   name: Publish to PyPI
   on:
     push:
       tags: ["v*.*.*"]
   jobs:
     build-and-publish:
       runs-on: ubuntu-latest
       environment: release
       permissions:
         id-token: write   # required for OIDC trusted publishing
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with:
             python-version: "3.12"
         - run: python -m pip install build
         - run: python -m build
         - uses: pypa/gh-action-pypi-publish@release/v1
   ```

3. From then on, `git tag vX.Y.Z && git push --tags` is your entire release process.

## 8. Post-release

- [ ] Confirm `pip install replayio` works from a machine you didn't build the
      package on
- [ ] Open a GitHub Release from the tag, paste the changelog entry
- [ ] Bump the version in `pyproject.toml` / `_version.py` to the next dev version
      (e.g. `1.0.1.dev0`) so accidental re-releases are obviously non-final

## Troubleshooting

| Problem | Likely cause |
|---|---|
| `File already exists` on upload | You can never overwrite a version on PyPI — bump the version number |
| `403 Forbidden` on upload | Wrong/expired API token, or token scoped to the wrong project |
| Package installs but `import replayio` fails | Check `[tool.setuptools.packages.find] where = ["src"]` matches your actual layout |
| README renders as plain text on PyPI | Ensure `readme = "README.md"` is set in `pyproject.toml` (Markdown is auto-detected from the extension) |
| Optional deps (`httpx`, `sqlalchemy`) not installing | Users need `pip install replayio[httpx]` / `[sqlalchemy]` / `[all]` explicitly — this is intentional to keep the core install light |
