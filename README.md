# asm-differ

Nice differ for assembly code (currently MIPS, but should be easy to hack to support other instruction sets).

![](screenshot.png)

## Dependencies

- Python >= 3.6
- `python3 -m pip install --user colorama ansiwrap attrs`

## Usage

Create a file `diff-settings.sh` in some directory (see the one in this repo for an example). Then from that directory, run

```
/path/to/diff.sh [flags] (function|rom addr)
```

The `-o` flag is recommended. See the script for more details.
