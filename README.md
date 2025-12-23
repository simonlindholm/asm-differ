# asm-differ

Diff viewer for assembly code, primarily for use in matching decompilation projects.
This is currently the default viewer used by [decomp.me](https://decomp.me/). 
Supports MIPS, PPC, AArch64, ARM32, SH2, SH4, m68k and (to limited extent) x86; should be easy to hack to support other instruction sets.

For a modern alternative, see also [objdiff](https://github.com/encounter/objdiff).

![](screenshot.png)

## Dependencies

- Python >= 3.6
- `python3 -m pip install --user colorama watchdog levenshtein cxxfilt`

## Usage

Create a file `diff_settings.py` in some directory (see the one in this repo for an example). Then from that directory, run

```bash
/path/to/diff.py [flags] (function|rom addr)
```

Recommended flags are `-mwo` (automatically run `make` on source file changes, and include symbols in diff). See `--help` for more details.

`diff.py` can be added as a project dependency either using git submodules, by copying diff.py directly into your repo, or via pip:
```
pip install 'asm-differ @ git+https://github.com/simonlindholm/asm-differ.git'
```
In the last mentioned case, run `asm-differ` instead of diff.py.

### Tab completion

[argcomplete](https://kislyuk.github.io/argcomplete/) can be optionally installed (with `python3 -m pip install argcomplete`) to enable tab completion in a bash shell, completing options and symbol names using the linker map. It also requires a bit more setup:

If invoking the script **exactly** as `./diff.py`, the following should be added to the `.bashrc` according to argcomplete's instructions:

```bash
eval "$(register-python-argcomplete ./diff.py)"
```

If that doesn't work, run `register-python-argcomplete ./diff.py` in your terminal and copy the output to `.bashrc`.

If setup correctly (don't forget to restart the shell), `complete | grep ./diff.py` should output:

```bash
complete -o bashdefault -o default -o nospace -F _python_argcomplete ./diff.py
```

Note for developers or for general troubleshooting: run `export _ARC_DEBUG=` to enable debug output during tab-completion, it may show otherwise silenced errors. Use `unset _ARC_DEBUG` or restart the terminal to disable.

### Contributing

Contributions are very welcome! Some notes on workflow:

`black` is used for code formatting. You can either run `black diff.py` manually, or set up a pre-commit hook:
```bash
pip install pre-commit black
pre-commit install
```

Type annotations are used for all Python code. `mypy` should pass without any errors. (This is all checked in CI.)

There are a handful of unit tests (test.py), however a comparison-based regression test suite is still missing.
There are loose plans on adding one using scratches from decomp.me as a corpus. Help on this front appreciated!

The targeted Python version is 3.7.
