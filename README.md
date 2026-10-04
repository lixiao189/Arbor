# Arbor

[![Tests](https://github.com/lixiao189/Arbor/actions/workflows/tests.yml/badge.svg?branch=master)](https://github.com/lixiao189/Arbor/actions/workflows/tests.yml)
[![Nightly](https://github.com/lixiao189/Arbor/actions/workflows/nightly.yml/badge.svg?branch=master)](https://github.com/lixiao189/Arbor/actions/workflows/nightly.yml)
[![Release](https://img.shields.io/github/v/release/lixiao189/Arbor?include_prereleases&sort=semver)](https://github.com/lixiao189/Arbor/releases)

Arbor is a small, keyboard-first mind map editor built with PyQt6. It borrows XMind's key bindings, so you can grow a map as fast as you can type: `Tab` adds a subtopic, `Enter` adds a sibling, and the arrow keys move around the tree. Topics spread out from the central topic in a balanced left/right layout.

You can also drag topics to rearrange them, select several at once, collapse branches, paste plain-text outlines as topics, and undo any change. Maps are saved as plain JSON `.mind` files.

## Download

Arbor is in alpha. The latest [nightly build](https://github.com/lixiao189/Arbor/releases/tag/nightly) of `master` is rebuilt every day:

- [macOS (Apple Silicon)](https://github.com/lixiao189/Arbor/releases/download/nightly/Arbor-macos-arm64.zip) – unsigned; right-click the app and choose Open the first time
- [Windows (x86_64)](https://github.com/lixiao189/Arbor/releases/download/nightly/Arbor-windows-x86_64.zip)
- [Linux (x86_64)](https://github.com/lixiao189/Arbor/releases/download/nightly/Arbor-linux-x86_64.tar.gz)
- [Linux (aarch64)](https://github.com/lixiao189/Arbor/releases/download/nightly/Arbor-linux-aarch64.tar.gz)

## Quick start

Arbor needs [uv](https://docs.astral.sh/uv/) (Python 3.13).

```bash
uv run arbor            # start with a new map
uv run arbor notes.mind # open a file
```

See [docs/usage.md](docs/usage.md) for key bindings and how to use the editor,
and [docs/development.md](docs/development.md) for running tests and the source layout.
