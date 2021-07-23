#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
import argparse
import sys
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Match,
    NoReturn,
    Optional,
    Pattern,
    Set,
    Tuple,
    Type,
    Union,
)


def fail(msg: str) -> NoReturn:
    print(msg, file=sys.stderr)
    sys.exit(1)


def static_assert_unreachable(x: NoReturn) -> NoReturn:
    raise Exception("Unreachable! " + repr(x))


# Prefer to use diff_settings.py from the current working directory
sys.path.insert(0, ".")
try:
    import diff_settings
except ModuleNotFoundError:
    fail("Unable to find diff_settings.py in the same directory.")
sys.path.pop(0)

# ==== COMMAND-LINE ====

if __name__ == "__main__":
    try:
        import argcomplete  # type: ignore
    except ModuleNotFoundError:
        argcomplete = None

    parser = argparse.ArgumentParser(description="Diff MIPS, PPC or AArch64 assembly.")

    start_argument = parser.add_argument(
        "start",
        help="Function name or address to start diffing from.",
    )

    if argcomplete:

        def complete_symbol(
            prefix: str, parsed_args: argparse.Namespace, **kwargs: object
        ) -> List[str]:
            if not prefix or prefix.startswith("-"):
                # skip reading the map file, which would
                # result in a lot of useless completions
                return []
            config: Dict[str, Any] = {}
            diff_settings.apply(config, parsed_args)  # type: ignore
            mapfile = config.get("mapfile")
            if not mapfile:
                return []
            completes = []
            with open(mapfile) as f:
                data = f.read()
                # assume symbols are prefixed by a space character
                search = f" {prefix}"
                pos = data.find(search)
                while pos != -1:
                    # skip the space character in the search string
                    pos += 1
                    # assume symbols are suffixed by either a space
                    # character or a (unix-style) line return
                    spacePos = data.find(" ", pos)
                    lineReturnPos = data.find("\n", pos)
                    if lineReturnPos == -1:
                        endPos = spacePos
                    elif spacePos == -1:
                        endPos = lineReturnPos
                    else:
                        endPos = min(spacePos, lineReturnPos)
                    if endPos == -1:
                        match = data[pos:]
                        pos = -1
                    else:
                        match = data[pos:endPos]
                        pos = data.find(search, endPos)
                    completes.append(match)
            return completes

        setattr(start_argument, "completer", complete_symbol)

    parser.add_argument(
        "end",
        nargs="?",
        help="Address to end diff at.",
    )
    parser.add_argument(
        "-o",
        dest="diff_obj",
        action="store_true",
        help="Diff .o files rather than a whole binary. This makes it possible to "
        "see symbol names. (Recommended)",
    )
    parser.add_argument(
        "-e",
        "--elf",
        dest="diff_elf_symbol",
        metavar="SYMBOL",
        help="Diff a given function in two ELFs, one being stripped and the other "
        "one non-stripped. Requires objdump from binutils 2.33+.",
    )
    parser.add_argument(
        "--source",
        action="store_true",
        help="Show source code (if possible). Only works with -o and -e.",
    )
    parser.add_argument(
        "--source-old-binutils",
        action="store_true",
        help="Tweak --source handling to make it work with binutils < 2.33. Implies --source.",
    )
    parser.add_argument(
        "--inlines",
        action="store_true",
        help="Show inline function calls (if possible). Only works with -o and -e.",
    )
    parser.add_argument(
        "--base-asm",
        dest="base_asm",
        metavar="FILE",
        help="Read assembly from given file instead of configured base img.",
    )
    parser.add_argument(
        "--write-asm",
        dest="write_asm",
        metavar="FILE",
        help="Write the current assembly output to file, e.g. for use with --base-asm.",
    )
    parser.add_argument(
        "-m",
        "--make",
        dest="make",
        action="store_true",
        help="Automatically run 'make' on the .o file or binary before diffing.",
    )
    parser.add_argument(
        "-l",
        "--skip-lines",
        dest="skip_lines",
        type=int,
        default=0,
        metavar="LINES",
        help="Skip the first N lines of output.",
    )
    parser.add_argument(
        "-s",
        "--stop-jr-ra",
        dest="stop_jrra",
        action="store_true",
        help="Stop disassembling at the first 'jr ra'. Some functions have multiple return points, so use with care!",
    )
    parser.add_argument(
        "-i",
        "--ignore-large-imms",
        dest="ignore_large_imms",
        action="store_true",
        help="Pretend all large enough immediates are the same.",
    )
    parser.add_argument(
        "-I",
        "--ignore-addr-diffs",
        dest="ignore_addr_diffs",
        action="store_true",
        help="Ignore address differences. Currently only affects AArch64.",
    )
    parser.add_argument(
        "-B",
        "--no-show-branches",
        dest="show_branches",
        action="store_false",
        help="Don't visualize branches/branch targets.",
    )
    parser.add_argument(
        "-S",
        "--base-shift",
        dest="base_shift",
        type=str,
        default="0",
        help="Diff position X in our img against position X + shift in the base img. "
        'Arithmetic is allowed, so e.g. |-S "0x1234 - 0x4321"| is a reasonable '
        "flag to pass if it is known that position 0x1234 in the base img syncs "
        "up with position 0x4321 in our img. Not supported together with -o.",
    )
    parser.add_argument(
        "-w",
        "--watch",
        dest="watch",
        action="store_true",
        help="Automatically update when source/object files change. "
        "Recommended in combination with -m.",
    )
    parser.add_argument(
        "--no-make",
        dest="no_make",
        action="store_true",
        help="Do not ask for confirmation when using --watch without --make",
    )
    parser.add_argument(
        "-3",
        "--threeway=prev",
        dest="threeway",
        action="store_const",
        const="prev",
        help="Show a three-way diff between target asm, current asm, and asm "
        "prior to -w rebuild. Requires -w.",
    )
    parser.add_argument(
        "-b",
        "--threeway=base",
        dest="threeway",
        action="store_const",
        const="base",
        help="Show a three-way diff between target asm, current asm, and asm "
        "when diff.py was started. Requires -w.",
    )
    parser.add_argument(
        "--width",
        dest="column_width",
        type=int,
        default=50,
        help="Sets the width of the left and right view column.",
    )
    parser.add_argument(
        "--algorithm",
        dest="algorithm",
        default="levenshtein",
        choices=["levenshtein", "difflib"],
        help="Diff algorithm to use. Levenshtein gives the minimum diff, while difflib "
        "aims for long sections of equal opcodes. Defaults to %(default)s.",
    )
    parser.add_argument(
        "--max-size",
        "--max-lines",
        dest="max_lines",
        type=int,
        default=1024,
        help="The maximum length of the diff, in lines.",
    )
    parser.add_argument(
        "--no-pager",
        action="store_true",
        help="Disable the pager; write output directly to stdout, then exit. "
        "Incompatible with --watch.",
    )
    parser.add_argument(
        "--format",
        choices=("color", "plain", "html"),
        default="color",
        help="Output format, default is color. --format=html implies --no-pager.",
    )
    parser.add_argument(
        "--web",
        dest="web_server",
        action="store_true",
        help="View diff in a browser. Implies --no-pager and --format=html.",
    )
    parser.add_argument(
        "--web-port",
        dest="http_server_port",
        type=int,
        default=8000,
        help="The port to run the http server on. Only with --web.",
    )
    parser.add_argument(
        "--browse",
        dest="run_browser",
        action="store_true",
        help="Run browser as set in settings. Only with --web.",
    )

    # Project-specific flags, e.g. different versions/make arguments.
    add_custom_arguments_fn = getattr(diff_settings, "add_custom_arguments", None)
    if add_custom_arguments_fn:
        add_custom_arguments_fn(parser)

    if argcomplete:
        argcomplete.autocomplete(parser)

# ==== IMPORTS ====

# (We do imports late to optimize auto-complete performance.)

import abc
import ast
from dataclasses import dataclass, field, replace
import difflib
import enum
import html
import itertools
import os
import queue
import re
import string
import subprocess
import threading
import time
import http.server
import urllib


MISSING_PREREQUISITES = (
    "Missing prerequisite python module {}. "
    "Run `python3 -m pip install --user colorama ansiwrap watchdog python-Levenshtein cxxfilt` to install prerequisites (cxxfilt only needed with --source)."
)

try:
    from colorama import Fore, Style  # type: ignore
    import ansiwrap  # type: ignore
    import watchdog  # type: ignore
except ModuleNotFoundError as e:
    fail(MISSING_PREREQUISITES.format(e.name))

# ==== CONFIG ====


@dataclass
class ProjectSettings:
    arch_str: str
    objdump_executable: str
    build_command: List[str]
    map_format: str
    mw_build_dir: str
    baseimg: Optional[str]
    myimg: Optional[str]
    mapfile: Optional[str]
    source_directories: Optional[List[str]]
    source_extensions: List[str]


@dataclass
class Config:
    arch: "ArchSettings"

    # Build/objdump options
    diff_obj: bool
    make: bool
    source: bool
    source_old_binutils: bool
    inlines: bool
    max_function_size_lines: int
    max_function_size_bytes: int

    # Display options
    formatter: "Formatter"
    threeway: Optional[str]
    base_shift: int
    skip_lines: int
    show_branches: bool
    stop_jrra: bool
    ignore_large_imms: bool
    ignore_addr_diffs: bool
    algorithm: str
    use_pager: bool
    web_server: bool
    run_browser: bool
    http_server_port: int
    log_http_requests: bool


def create_project_settings(settings: Dict[str, Any]) -> ProjectSettings:
    return ProjectSettings(
        arch_str=settings.get("arch", "mips"),
        baseimg=settings.get("baseimg"),
        myimg=settings.get("myimg"),
        mapfile=settings.get("mapfile"),
        build_command=settings.get(
            "make_command", ["make", *settings.get("makeflags", [])]
        ),
        source_directories=settings.get("source_directories"),
        source_extensions=settings.get(
            "source_extensions", [".c", ".h", ".cpp", ".hpp", ".s"]
        ),
        objdump_executable=get_objdump_executable(settings.get("objdump_executable")),
        map_format=settings.get("map_format", "gnu"),
        mw_build_dir=settings.get("mw_build_dir", "build/"),
    )


def create_config(args: argparse.Namespace, project: ProjectSettings) -> Config:
    formatter: Formatter
    if args.web_server:
        args.format = "html"
    if args.format == "plain":
        formatter = PlainFormatter(column_width=args.column_width)
    elif args.format == "color":
        formatter = AnsiFormatter(column_width=args.column_width)
    elif args.format == "html":
        formatter = HtmlFormatter()
    else:
        raise ValueError(f"Unsupported --format: {args.format}")

    return Config(
        arch=get_arch(project.arch_str),
        # Build/objdump options
        diff_obj=args.diff_obj,
        make=args.make,
        source=args.source or args.source_old_binutils,
        source_old_binutils=args.source_old_binutils,
        inlines=args.inlines,
        max_function_size_lines=args.max_lines,
        max_function_size_bytes=args.max_lines * 4,
        # Display options
        formatter=formatter,
        threeway=args.threeway,
        base_shift=eval_int(
            args.base_shift, "Failed to parse --base-shift (-S) argument as an integer."
        ),
        skip_lines=args.skip_lines,
        show_branches=args.show_branches,
        stop_jrra=args.stop_jrra,
        ignore_large_imms=args.ignore_large_imms,
        ignore_addr_diffs=args.ignore_addr_diffs,
        algorithm=args.algorithm,
        use_pager=args.format != "html" and not args.no_pager and not args.web_server,
        web_server=args.web_server,
        run_browser=args.run_browser,
        http_server_port=args.http_server_port,
        log_http_requests=False,
    )


def get_objdump_executable(objdump_executable: Optional[str]) -> str:
    if objdump_executable is not None:
        return objdump_executable

    for objdump_cand in ["mips-linux-gnu-objdump", "mips64-elf-objdump"]:
        try:
            subprocess.check_call(
                [objdump_cand, "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return objdump_cand
        except subprocess.CalledProcessError:
            pass
        except FileNotFoundError:
            pass

    return fail(
        "Missing binutils; please ensure mips-linux-gnu-objdump or mips64-elf-objdump exist, or configure objdump_executable."
    )


def get_arch(arch_str: str) -> "ArchSettings":
    if arch_str == "mips":
        return MIPS_SETTINGS
    if arch_str == "aarch64":
        return AARCH64_SETTINGS
    if arch_str == "ppc":
        return PPC_SETTINGS
    return fail(f"Unknown architecture: {arch_str}")


BUFFER_CMD: List[str] = ["tail", "-c", str(10 ** 9)]

# -S truncates long lines instead of wrapping them
# -R interprets color escape sequences
# -i ignores case when searching
# -c something about how the screen gets redrawn; I don't remember the purpose
# -#6 makes left/right arrow keys scroll by 6 characters
LESS_CMD: List[str] = ["less", "-SRic", "-#6"]

DEBOUNCE_DELAY: float = 0.1

# ==== FORMATTING ====


@enum.unique
class BasicFormat(enum.Enum):
    NONE = enum.auto()
    IMMEDIATE = enum.auto()
    STACK = enum.auto()
    REGISTER = enum.auto()
    DELAY_SLOT = enum.auto()
    DIFF_CHANGE = enum.auto()
    DIFF_ADD = enum.auto()
    DIFF_REMOVE = enum.auto()
    SOURCE_FILENAME = enum.auto()
    SOURCE_FUNCTION = enum.auto()
    SOURCE_OTHER = enum.auto()


@dataclass(frozen=True)
class RotationFormat:
    group: str
    index: int
    key: str


@dataclass(frozen=True)
class RegDiffFormat(RotationFormat):
    pass


@dataclass(frozen=True)
class StackDiffFormat(RotationFormat):
    pass


@dataclass(frozen=True)
class BranchFormat(RotationFormat):
    from_line: int
    to_line: int
    is_target: bool


Format = Union[BasicFormat, RegDiffFormat, StackDiffFormat, BranchFormat]
FormatRegDiffFunction = Callable[[str], RegDiffFormat]
FormatStackDiffFunction = Callable[[str], StackDiffFormat]
FormatRegOrStackDiffFunction = Union[FormatRegDiffFunction, FormatStackDiffFunction]
FormatBranchFunction = Callable[
    [str, Optional[int], Optional[int], Optional[bool]], BranchFormat
]


class Text:
    segments: List[Tuple[str, Format]]

    def __init__(
        self, line: Optional[str] = None, f: Format = BasicFormat.NONE
    ) -> None:
        self.segments = []
        if line is not None:
            self.segments.append((line, f))
        elif f is not BasicFormat.NONE:
            raise ValueError("Text constructor provided `f`, but no line to format")

    def reformat(self, f: Format) -> "Text":
        return Text(self.plain(), f)

    def plain(self) -> str:
        return "".join(s for s, f in self.segments)

    def __repr__(self) -> str:
        return f"<Text: {self.plain()!r}>"

    def __str__(self) -> str:
        # Use Formatter.apply(...) instead
        return NotImplemented

    def __eq__(self, other: object) -> bool:
        return NotImplemented

    def __add__(self, other: Union["Text", str]) -> "Text":
        if isinstance(other, str):
            other = Text(other)
        result = Text()
        result.segments = self.segments + other.segments
        return result

    def __radd__(self, other: Union["Text", str]) -> "Text":
        if isinstance(other, str):
            other = Text(other)
        result = Text()
        result.segments = other.segments + self.segments
        return result

    def finditer(self, pat: Pattern[str]) -> Iterator[Match[str]]:
        """Replacement for `pat.finditer(text)` that operates on the inner text,
        and returns the exact same matches as `Text.sub(pat, ...)`."""
        for chunk, f in self.segments:
            for match in pat.finditer(chunk):
                yield match

    def sub(self, pat: Pattern[str], sub_fn: Callable[[Match[str]], "Text"]) -> "Text":
        result = Text()
        for chunk, f in self.segments:
            i = 0
            for match in pat.finditer(chunk):
                start, end = match.start(), match.end()
                assert i <= start <= end <= len(chunk)
                sub = sub_fn(match)
                result.segments.append((chunk[i:start], f))
                result.segments.extend(sub.segments)
                i = end
            result.segments.append((chunk[i:], f))
        return result


class Formatter(abc.ABC):
    @abc.abstractmethod
    def apply_format(self, chunk: str, f: Format) -> str:
        """Apply the formatting `f` to `chunk` and escape the contents."""
        ...

    @abc.abstractmethod
    def table(
        self, header: Optional[Tuple[str, ...]], lines: List[Tuple[str, ...]]
    ) -> str:
        """Format a multi-column table with an optional `header`"""
        ...

    def apply(self, text: Text) -> str:
        return "".join(self.apply_format(chunk, f) for chunk, f in text.segments)


@dataclass
class PlainFormatter(Formatter):
    column_width: int

    def apply_format(self, chunk: str, f: Format) -> str:
        return chunk

    def table(
        self, header: Optional[Tuple[str, ...]], lines: List[Tuple[str, ...]]
    ) -> str:
        if header:
            lines = [header] + lines
        return "\n".join(
            "".join(x.ljust(self.column_width) for x in line) for line in lines
        )


@dataclass
class AnsiFormatter(Formatter):
    BASIC_ANSI_CODES = {
        BasicFormat.NONE: "",
        BasicFormat.IMMEDIATE: Fore.LIGHTBLUE_EX,
        BasicFormat.STACK: Fore.YELLOW,
        BasicFormat.REGISTER: Fore.YELLOW,
        BasicFormat.DELAY_SLOT: Fore.LIGHTBLACK_EX,
        BasicFormat.DIFF_CHANGE: Fore.LIGHTBLUE_EX,
        BasicFormat.DIFF_ADD: Fore.GREEN,
        BasicFormat.DIFF_REMOVE: Fore.RED,
        BasicFormat.SOURCE_FILENAME: Style.BRIGHT,
        # Underline (not in colorama) + bright
        BasicFormat.SOURCE_FUNCTION: Style.BRIGHT + "\u001b[4m",
        BasicFormat.SOURCE_OTHER: Style.DIM,
    }

    ROTATION_ANSI_COLORS = [
        Fore.MAGENTA,
        Fore.CYAN,
        Fore.GREEN,
        Fore.RED,
        Fore.LIGHTYELLOW_EX,
        Fore.LIGHTMAGENTA_EX,
        Fore.LIGHTCYAN_EX,
        Fore.LIGHTGREEN_EX,
        Fore.LIGHTBLACK_EX,
    ]

    column_width: int

    def apply_format(self, chunk: str, f: Format) -> str:
        if f == BasicFormat.NONE:
            return chunk
        if isinstance(f, BasicFormat):
            ansi_code = self.BASIC_ANSI_CODES[f]
        elif isinstance(f, RotationFormat):
            ansi_code = self.ROTATION_ANSI_COLORS[
                f.index % len(self.ROTATION_ANSI_COLORS)
            ]
        else:
            static_assert_unreachable(f)
        return f"{ansi_code}{chunk}{Style.RESET_ALL}"

    def table(
        self, header: Optional[Tuple[str, ...]], lines: List[Tuple[str, ...]]
    ) -> str:
        if header:
            lines = [header] + lines
        return "\n".join("".join(self.ansi_ljust(x) for x in line) for line in lines)

    def ansi_ljust(self, s: str) -> str:
        """Like s.ljust(width), but accounting for ANSI colors."""
        needed: int = self.column_width - ansiwrap.ansilen(s)
        if needed > 0:
            return s + " " * needed
        else:
            return s


@dataclass
class HtmlFormatter(Formatter):
    rotation_formats: int = 9

    def apply_format(self, chunk: str, f: Format) -> str:
        chunk = html.escape(chunk)
        if f == BasicFormat.NONE:
            return chunk
        id_attr = ""
        data_attr = ""
        if isinstance(f, BasicFormat):
            class_name = f.name.lower().replace("_", "-")
        elif isinstance(f, RotationFormat):
            class_name = f"rotation-{f.index % self.rotation_formats}"
            rotation_key = html.escape(f"{f.group};{f.key}", quote=True)
            data_attr = f'data-rotation="{rotation_key}"'
        else:
            static_assert_unreachable(f)

        if isinstance(f, BranchFormat):
            if f.is_target is None:
                static_assert_unreachable(f)
            branch_base_id = f"branch-{f.group}-{f.from_line}"

            branches_class = html.escape(branch_base_id, quote=True)
            class_name += f" branch-indicator {branches_class}"
            data_attr += f' data-branches-class="{branches_class}"'

            branch_target_id = html.escape(f"{branch_base_id}-target", quote=True)
            if f.is_target:
                id = html.escape(branch_target_id, quote=True)
                id_attr = f'id="{id}"'
            else:
                data_attr += f' data-branch-target="{branch_target_id}"'

        return f"<span class='{class_name}' {id_attr} {data_attr}>{chunk}</span>"

    def table(
        self, header: Optional[Tuple[str, ...]], lines: List[Tuple[str, ...]]
    ) -> str:
        def table_row(line: Tuple[str, ...], cell_el: str) -> str:
            output_row = "    <tr>"
            for cell in line:
                output_row += f"<{cell_el}>{cell}</{cell_el}>"
            output_row += "</tr>\n"
            return output_row

        output = "<table class='diff'>\n"
        if header:
            output += "  <thead>\n"
            output += table_row(header, "th")
            output += "  </thead>\n"
        output += "  <tbody>\n"
        output += "".join(table_row(line, "td") for line in lines)
        output += "  </tbody>\n"
        output += "</table>\n"
        return output


def format_fields(
    pat: Pattern[str],
    out1: Text,
    out2: Text,
    color1: FormatRegOrStackDiffFunction,
    color2: Optional[FormatRegOrStackDiffFunction] = None,
) -> Tuple[Text, Text]:
    diffs = [
        of.group() != nf.group()
        for (of, nf) in zip(out1.finditer(pat), out2.finditer(pat))
    ]

    it = iter(diffs)

    def maybe_color(color: FormatRegOrStackDiffFunction, s: str) -> Text:
        return Text(s, color(s)) if next(it, False) else Text(s)

    out1 = out1.sub(pat, lambda m: maybe_color(color1, m.group()))
    it = iter(diffs)
    out2 = out2.sub(pat, lambda m: maybe_color(color2 or color1, m.group()))

    return out1, out2


def reg_formatter(group: str, base_index: int) -> FormatRegDiffFunction:
    reg_formats: Dict[str, Format] = {}

    def reg_format(s: str) -> RegDiffFormat:
        f = reg_formats.get(s)
        if f is None:
            index = len(reg_formats) + base_index
            f = RegDiffFormat(key=s, index=index, group=group)
            reg_formats[s] = f
        return f

    return reg_format


def stack_formatter(group: str, base_index: int) -> FormatStackDiffFunction:
    stack_formats: Dict[str, Format] = {}

    def stack_format(s: str) -> StackDiffFormat:
        f = stack_formats.get(s)
        if f is None:
            index = len(stack_formats) + base_index
            f = StackDiffFormat(key=s, index=index, group=group)
            stack_formats[s] = f
        return f

    return stack_format


def branch_formatter(group: str, base_index: int) -> FormatBranchFunction:
    branch_formats: Dict[str, Format] = {}

    def branch_format(
        s: str,
        from_line: Optional[int] = None,
        to_line: Optional[int] = None,
        is_target: Optional[bool] = None,
    ) -> BranchFormat:
        f = branch_formats.get(s)
        if f is None:
            index = len(branch_formats) + base_index
            # is_target = False is temporary and meant to be set by further branch_format() calls
            f = BranchFormat(
                key=s,
                index=index,
                group=group,
                from_line=from_line,
                to_line=to_line,
                is_target=False,
            )
            branch_formats[s] = f
        if is_target is not None:
            newFmtArgs = f.__dict__.copy()
            newFmtArgs["is_target"] = is_target
            f = BranchFormat(**newFmtArgs)
        return f

    return branch_format


# ==== LOGIC ====

ObjdumpCommand = Tuple[List[str], str, Optional[str]]


def maybe_eval_int(expr: str) -> Optional[int]:
    try:
        ret = ast.literal_eval(expr)
        if not isinstance(ret, int):
            raise Exception("not an integer")
        return ret
    except Exception:
        return None


def eval_int(expr: str, emsg: str) -> int:
    ret = maybe_eval_int(expr)
    if ret is None:
        fail(emsg)
    return ret


def eval_line_num(expr: str) -> int:
    return int(expr.strip().replace(":", ""), 16)


def run_make(target: str, project: ProjectSettings) -> None:
    subprocess.check_call(project.build_command + [target])


def run_make_capture_output(
    target: str, project: ProjectSettings
) -> "subprocess.CompletedProcess[bytes]":
    return subprocess.run(
        project.build_command + [target],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )


def restrict_to_function(dump: str, fn_name: str, config: Config) -> str:
    out: List[str] = []
    search = f"<{fn_name}>:"
    found = False
    for line in dump.split("\n"):
        if found:
            if len(out) >= config.max_function_size_lines:
                break
            out.append(line)
        elif search in line:
            found = True
    return "\n".join(out)


def maybe_get_objdump_source_flags(config: Config) -> List[str]:
    if not config.source:
        return []

    flags = [
        "--source",
        "-l",
    ]

    if not config.source_old_binutils:
        flags.append("--source-comment=│ ")

    if config.inlines:
        flags.append("--inlines")

    return flags


def run_objdump(cmd: ObjdumpCommand, config: Config, project: ProjectSettings) -> str:
    flags, target, restrict = cmd
    try:
        out = subprocess.run(
            [project.objdump_executable] + config.arch.arch_flags + flags + [target],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        ).stdout
    except subprocess.CalledProcessError as e:
        print(e.stdout)
        print(e.stderr)
        if "unrecognized option '--source-comment" in e.stderr:
            fail("** Try using --source-old-binutils instead of --source **")
        raise e

    if restrict is not None:
        return restrict_to_function(out, restrict, config)
    return out


def search_map_file(
    fn_name: str, project: ProjectSettings
) -> Tuple[Optional[str], Optional[int]]:
    if not project.mapfile:
        fail(f"No map file configured; cannot find function {fn_name}.")

    try:
        with open(project.mapfile) as f:
            contents = f.read()
    except Exception:
        fail(f"Failed to open map file {project.mapfile} for reading.")

    if project.map_format == "gnu":
        lines = contents.split("\n")

        try:
            cur_objfile = None
            ram_to_rom = None
            cands = []
            last_line = ""
            for line in lines:
                if line.startswith(" .text"):
                    cur_objfile = line.split()[3]
                if "load address" in line:
                    tokens = last_line.split() + line.split()
                    ram = int(tokens[1], 0)
                    rom = int(tokens[5], 0)
                    ram_to_rom = rom - ram
                if line.endswith(" " + fn_name):
                    ram = int(line.split()[0], 0)
                    if cur_objfile is not None and ram_to_rom is not None:
                        cands.append((cur_objfile, ram + ram_to_rom))
                last_line = line
        except Exception as e:
            import traceback

            traceback.print_exc()
            fail(f"Internal error while parsing map file")

        if len(cands) > 1:
            fail(f"Found multiple occurrences of function {fn_name} in map file.")
        if len(cands) == 1:
            return cands[0]
    elif project.map_format == "mw":
        find = re.findall(
            re.compile(
                #            ram   elf rom
                r"  \S+ \S+ (\S+) (\S+)  . "
                + fn_name
                #                                         object name
                + r"(?: \(entry of \.(?:init|text)\))? \t(\S+)"
            ),
            contents,
        )
        if len(find) > 1:
            fail(f"Found multiple occurrences of function {fn_name} in map file.")
        if len(find) == 1:
            rom = int(find[0][1], 16)
            objname = find[0][2]
            # The metrowerks linker map format does not contain the full object path,
            # so we must complete it manually.
            objfiles = [
                os.path.join(dirpath, f)
                for dirpath, _, filenames in os.walk(project.mw_build_dir)
                for f in filenames
                if f == objname
            ]
            if len(objfiles) > 1:
                all_objects = "\n".join(objfiles)
                fail(
                    f"Found multiple objects of the same name {objname} in {project.mw_build_dir}, "
                    f"cannot determine which to diff against: \n{all_objects}"
                )
            if len(objfiles) == 1:
                objfile = objfiles[0]
                # TODO Currently the ram-rom conversion only works for diffing ELF
                # executables, but it would likely be more convenient to diff DOLs.
                # At this time it is recommended to always use -o when running the diff
                # script as this mode does not make use of the ram-rom conversion.
                return objfile, rom
    else:
        fail(f"Linker map format {project.map_format} unrecognised.")
    return None, None


def dump_elf(
    start: str,
    end: Optional[str],
    diff_elf_symbol: str,
    config: Config,
    project: ProjectSettings,
) -> Tuple[str, ObjdumpCommand, ObjdumpCommand]:
    if not project.baseimg or not project.myimg:
        fail("Missing myimg/baseimg in config.")
    if config.base_shift:
        fail("--base-shift not compatible with -e")

    start_addr = eval_int(start, "Start address must be an integer expression.")

    if end is not None:
        end_addr = eval_int(end, "End address must be an integer expression.")
    else:
        end_addr = start_addr + config.max_function_size_bytes

    flags1 = [
        f"--start-address={start_addr}",
        f"--stop-address={end_addr}",
    ]

    flags2 = [
        f"--disassemble={diff_elf_symbol}",
    ]

    objdump_flags = ["-drz", "-j", ".text"]
    return (
        project.myimg,
        (objdump_flags + flags1, project.baseimg, None),
        (
            objdump_flags + flags2 + maybe_get_objdump_source_flags(config),
            project.myimg,
            None,
        ),
    )


def dump_objfile(
    start: str, end: Optional[str], config: Config, project: ProjectSettings
) -> Tuple[str, ObjdumpCommand, ObjdumpCommand]:
    if config.base_shift:
        fail("--base-shift not compatible with -o")
    if end is not None:
        fail("end address not supported together with -o")
    if start.startswith("0"):
        fail("numerical start address not supported with -o; pass a function name")

    objfile, _ = search_map_file(start, project)
    if not objfile:
        fail("Not able to find .o file for function.")

    if config.make:
        run_make(objfile, project)

    if not os.path.isfile(objfile):
        fail(f"Not able to find .o file for function: {objfile} is not a file.")

    refobjfile = "expected/" + objfile
    if not os.path.isfile(refobjfile):
        fail(f'Please ensure an OK .o file exists at "{refobjfile}".')

    objdump_flags = ["-drz"]
    return (
        objfile,
        (objdump_flags, refobjfile, start),
        (objdump_flags + maybe_get_objdump_source_flags(config), objfile, start),
    )


def dump_binary(
    start: str, end: Optional[str], config: Config, project: ProjectSettings
) -> Tuple[str, ObjdumpCommand, ObjdumpCommand]:
    if not project.baseimg or not project.myimg:
        fail("Missing myimg/baseimg in config.")
    if config.make:
        run_make(project.myimg, project)
    start_addr = maybe_eval_int(start)
    if start_addr is None:
        _, start_addr = search_map_file(start, project)
        if start_addr is None:
            fail("Not able to find function in map file.")
    if end is not None:
        end_addr = eval_int(end, "End address must be an integer expression.")
    else:
        end_addr = start_addr + config.max_function_size_bytes
    objdump_flags = ["-Dz", "-bbinary", "-EB"]
    flags1 = [
        f"--start-address={start_addr + config.base_shift}",
        f"--stop-address={end_addr + config.base_shift}",
    ]
    flags2 = [f"--start-address={start_addr}", f"--stop-address={end_addr}"]
    return (
        project.myimg,
        (objdump_flags + flags1, project.baseimg, None),
        (objdump_flags + flags2, project.myimg, None),
    )


class DifferenceNormalizer:
    def __init__(self, config: Config) -> None:
        self.config = config

    def normalize(self, mnemonic: str, row: str) -> str:
        """This should be called exactly once for each line."""
        row = self._normalize_arch_specific(mnemonic, row)
        if self.config.ignore_large_imms:
            row = re.sub(self.config.arch.re_large_imm, "<imm>", row)
        return row

    def _normalize_arch_specific(self, mnemonic: str, row: str) -> str:
        return row


class DifferenceNormalizerAArch64(DifferenceNormalizer):
    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._adrp_pair_registers: Set[str] = set()

    def _normalize_arch_specific(self, mnemonic: str, row: str) -> str:
        if self.config.ignore_addr_diffs:
            row = self._normalize_adrp_differences(mnemonic, row)
            row = self._normalize_bl(mnemonic, row)
        return row

    def _normalize_bl(self, mnemonic: str, row: str) -> str:
        if mnemonic != "bl":
            return row

        row, _ = split_off_branch(row)
        return row

    def _normalize_adrp_differences(self, mnemonic: str, row: str) -> str:
        """Identifies ADRP + LDR/ADD pairs that are used to access the GOT and
        suppresses any immediate differences.

        Whenever an ADRP is seen, the destination register is added to the set of registers
        that are part of an ADRP + LDR/ADD pair. Registers are removed from the set as soon
        as they are used for an LDR or ADD instruction which completes the pair.

        This method is somewhat crude but should manage to detect most such pairs.
        """
        row_parts = row.split("\t", 1)
        if mnemonic == "adrp":
            self._adrp_pair_registers.add(row_parts[1].strip().split(",")[0])
            row, _ = split_off_branch(row)
        elif mnemonic == "ldr":
            for reg in self._adrp_pair_registers:
                # ldr xxx, [reg]
                # ldr xxx, [reg, <imm>]
                if f", [{reg}" in row_parts[1]:
                    self._adrp_pair_registers.remove(reg)
                    return normalize_imms(row, AARCH64_SETTINGS)
        elif mnemonic == "add":
            for reg in self._adrp_pair_registers:
                # add reg, reg, <imm>
                if row_parts[1].startswith(f"{reg}, {reg}, "):
                    self._adrp_pair_registers.remove(reg)
                    return normalize_imms(row, AARCH64_SETTINGS)

        return row


@dataclass
class ArchSettings:
    re_int: Pattern[str]
    re_comment: Pattern[str]
    re_reg: Pattern[str]
    re_sprel: Pattern[str]
    re_large_imm: Pattern[str]
    re_imm: Pattern[str]
    branch_instructions: Set[str]
    instructions_with_address_immediates: Set[str]
    forbidden: Set[str] = field(default_factory=lambda: set(string.ascii_letters + "_"))
    arch_flags: List[str] = field(default_factory=list)
    branch_likely_instructions: Set[str] = field(default_factory=set)
    difference_normalizer: Type[DifferenceNormalizer] = DifferenceNormalizer


MIPS_BRANCH_LIKELY_INSTRUCTIONS = {
    "beql",
    "bnel",
    "beqzl",
    "bnezl",
    "bgezl",
    "bgtzl",
    "blezl",
    "bltzl",
    "bc1tl",
    "bc1fl",
}
MIPS_BRANCH_INSTRUCTIONS = MIPS_BRANCH_LIKELY_INSTRUCTIONS.union(
    {
        "b",
        "beq",
        "bne",
        "beqz",
        "bnez",
        "bgez",
        "bgtz",
        "blez",
        "bltz",
        "bc1t",
        "bc1f",
    }
)

AARCH64_BRANCH_INSTRUCTIONS = {
    "bl",
    "b",
    "b.eq",
    "b.ne",
    "b.cs",
    "b.hs",
    "b.cc",
    "b.lo",
    "b.mi",
    "b.pl",
    "b.vs",
    "b.vc",
    "b.hi",
    "b.ls",
    "b.ge",
    "b.lt",
    "b.gt",
    "b.le",
    "cbz",
    "cbnz",
    "tbz",
    "tbnz",
}

PPC_BRANCH_INSTRUCTIONS = {
    "b",
    "beq",
    "beq+",
    "beq-",
    "bne",
    "bne+",
    "bne-",
    "blt",
    "blt+",
    "blt-",
    "ble",
    "ble+",
    "ble-",
    "bdnz",
    "bdnz+",
    "bdnz-",
    "bge",
    "bge+",
    "bge-",
    "bgt",
    "bgt+",
    "bgt-",
}

MIPS_SETTINGS = ArchSettings(
    re_int=re.compile(r"[0-9]+"),
    re_comment=re.compile(r"<.*?>"),
    re_reg=re.compile(
        r"\$?\b(a[0-3]|t[0-9]|s[0-8]|at|v[01]|f[12]?[0-9]|f3[01]|k[01]|fp|ra|zero)\b"
    ),
    re_sprel=re.compile(r"(?<=,)([0-9]+|0x[0-9a-f]+)\(sp\)"),
    re_large_imm=re.compile(r"-?[1-9][0-9]{2,}|-?0x[0-9a-f]{3,}"),
    re_imm=re.compile(r"(\b|-)([0-9]+|0x[0-9a-fA-F]+)\b(?!\(sp)|%(lo|hi)\([^)]*\)"),
    arch_flags=["-m", "mips:4300"],
    branch_likely_instructions=MIPS_BRANCH_LIKELY_INSTRUCTIONS,
    branch_instructions=MIPS_BRANCH_INSTRUCTIONS,
    instructions_with_address_immediates=MIPS_BRANCH_INSTRUCTIONS.union({"jal", "j"}),
)

AARCH64_SETTINGS = ArchSettings(
    re_int=re.compile(r"[0-9]+"),
    re_comment=re.compile(r"(<.*?>|//.*$)"),
    # GPRs and FP registers: X0-X30, W0-W30, [DSHQ]0..31
    # The zero registers and SP should not be in this list.
    re_reg=re.compile(r"\$?\b([dshq][12]?[0-9]|[dshq]3[01]|[xw][12]?[0-9]|[xw]30)\b"),
    re_sprel=re.compile(r"sp, #-?(0x[0-9a-fA-F]+|[0-9]+)\b"),
    re_large_imm=re.compile(r"-?[1-9][0-9]{2,}|-?0x[0-9a-f]{3,}"),
    re_imm=re.compile(r"(?<!sp, )#-?(0x[0-9a-fA-F]+|[0-9]+)\b"),
    branch_instructions=AARCH64_BRANCH_INSTRUCTIONS,
    instructions_with_address_immediates=AARCH64_BRANCH_INSTRUCTIONS.union({"adrp"}),
    difference_normalizer=DifferenceNormalizerAArch64,
)

PPC_SETTINGS = ArchSettings(
    re_int=re.compile(r"[0-9]+"),
    re_comment=re.compile(r"(<.*?>|//.*$)"),
    re_reg=re.compile(r"\$?\b([rf][0-9]+)\b"),
    re_sprel=re.compile(r"(?<=,)(-?[0-9]+|-?0x[0-9a-f]+)\(r1\)"),
    re_large_imm=re.compile(r"-?[1-9][0-9]{2,}|-?0x[0-9a-f]{3,}"),
    re_imm=re.compile(r"(\b|-)([0-9]+|0x[0-9a-fA-F]+)\b(?!\(r1)|[^@]*@(ha|h|lo)"),
    branch_instructions=PPC_BRANCH_INSTRUCTIONS,
    instructions_with_address_immediates=PPC_BRANCH_INSTRUCTIONS.union({"bl"}),
)


def hexify_int(row: str, pat: Match[str], arch: ArchSettings) -> str:
    full = pat.group(0)
    if len(full) <= 1:
        # leave one-digit ints alone
        return full
    start, end = pat.span()
    if start and row[start - 1] in arch.forbidden:
        return full
    if end < len(row) and row[end] in arch.forbidden:
        return full
    return hex(int(full))


def parse_relocated_line(line: str) -> Tuple[str, str, str]:
    try:
        ind2 = line.rindex(",")
    except ValueError:
        try:
            ind2 = line.rindex("\t")
        except ValueError:
            ind2 = line.rindex(" ")
    before = line[: ind2 + 1]
    after = line[ind2 + 1 :]
    ind2 = after.find("(")
    if ind2 == -1:
        imm, after = after, ""
    else:
        imm, after = after[:ind2], after[ind2:]
    if imm == "0x0":
        imm = "0"
    return before, imm, after


def process_mips_reloc(row: str, prev: str, arch: ArchSettings) -> str:
    before, imm, after = parse_relocated_line(prev)
    repl = row.split()[-1]
    if imm != "0":
        # MIPS uses relocations with addends embedded in the code as immediates.
        # If there is an immediate, show it as part of the relocation. Ideally
        # we'd show this addend in both %lo/%hi, but annoyingly objdump's output
        # doesn't include enough information to pair up %lo's and %hi's...
        # TODO: handle unambiguous cases where all addends for a symbol are the
        # same, or show "+???".
        mnemonic = prev.split()[0]
        if (
            mnemonic in arch.instructions_with_address_immediates
            and not imm.startswith("0x")
        ):
            imm = "0x" + imm
        repl += "+" + imm if int(imm, 0) > 0 else imm
    if "R_MIPS_LO16" in row:
        repl = f"%lo({repl})"
    elif "R_MIPS_HI16" in row:
        # Ideally we'd pair up R_MIPS_LO16 and R_MIPS_HI16 to generate a
        # correct addend for each, but objdump doesn't give us the order of
        # the relocations, so we can't find the right LO16. :(
        repl = f"%hi({repl})"
    elif "R_MIPS_26" in row:
        # Function calls
        pass
    elif "R_MIPS_PC16" in row:
        # Branch to glabel. This gives confusing output, but there's not much
        # we can do here.
        pass
    else:
        assert False, f"unknown relocation type '{row}' for line '{prev}'"
    return before + repl + after


def process_ppc_reloc(row: str, prev: str) -> str:
    assert any(
        r in row for r in ["R_PPC_REL24", "R_PPC_ADDR16", "R_PPC_EMB_SDA21"]
    ), f"unknown relocation type '{row}' for line '{prev}'"
    before, imm, after = parse_relocated_line(prev)
    repl = row.split()[-1]
    if "R_PPC_REL24" in row:
        # function calls
        pass
    elif "R_PPC_ADDR16_HI" in row:
        # absolute hi of addr
        repl = f"{repl}@h"
    elif "R_PPC_ADDR16_HA" in row:
        # adjusted hi of addr
        repl = f"{repl}@ha"
    elif "R_PPC_ADDR16_LO" in row:
        # lo of addr
        repl = f"{repl}@l"
    elif "R_PPC_ADDR16" in row:
        # 16-bit absolute addr
        if "+0x7" in repl:
            # remove the very large addends as they are an artifact of (label-_SDA(2)_BASE_)
            # computations and are unimportant in a diff setting.
            if int(repl.split("+")[1], 16) > 0x70000000:
                repl = repl.split("+")[0]
    elif "R_PPC_EMB_SDA21" in row:
        # small data area
        pass
    return before + repl + after


def pad_mnemonic(line: str) -> str:
    if "\t" not in line:
        return line
    mn, args = line.split("\t", 1)
    return f"{mn:<7s} {args}"


@dataclass
class Line:
    mnemonic: str
    diff_row: str
    original: str
    normalized_original: str
    line_num: str
    branch_target: Optional[str]
    source_lines: List[str]
    comment: Optional[str]


def process(lines: List[str], config: Config) -> List[Line]:
    arch = config.arch
    normalizer = arch.difference_normalizer(config)
    skip_next = False
    source_lines = []
    if not config.diff_obj:
        lines = lines[7:]
        if lines and not lines[-1]:
            lines.pop()

    output: List[Line] = []
    stop_after_delay_slot = False
    for row in lines:
        if config.diff_obj and (">:" in row or not row):
            continue

        if config.source and not config.source_old_binutils and (row and row[0] != " "):
            source_lines.append(row)
            continue

        if "R_AARCH64_" in row:
            # TODO: handle relocation
            continue

        if "R_MIPS_" in row:
            # N.B. Don't transform the diff rows, they already ignore immediates
            # if output[-1].diff_row != "<delay-slot>":
            # output[-1] = output[-1].replace(diff_row=process_mips_reloc(row, output[-1].row_with_imm, arch))
            new_original = process_mips_reloc(row, output[-1].original, arch)
            output[-1] = replace(output[-1], original=new_original)
            continue

        if "R_PPC_" in row:
            new_original = process_ppc_reloc(row, output[-1].original)
            output[-1] = replace(output[-1], original=new_original)
            continue

        # match source lines here to avoid matching relocation lines
        if (
            config.source
            and config.source_old_binutils
            and (row and not re.match(r"^ +[0-9a-f]+:\t", row))
        ):
            source_lines.append(row)
            continue

        m_comment = re.search(arch.re_comment, row)
        comment = m_comment[0] if m_comment else None
        row = re.sub(arch.re_comment, "", row)
        row = row.rstrip()
        tabs = row.split("\t")
        row = "\t".join(tabs[2:])
        line_num = tabs[0].strip()

        if "\t" in row:
            row_parts = row.split("\t", 1)
        else:
            # powerpc-eabi-objdump doesn't use tabs
            row_parts = [part.lstrip() for part in row.split(" ", 1)]
        mnemonic = row_parts[0].strip()

        if mnemonic not in arch.instructions_with_address_immediates:
            row = re.sub(arch.re_int, lambda m: hexify_int(row, m, arch), row)
        original = row
        normalized_original = normalizer.normalize(mnemonic, original)
        if skip_next:
            skip_next = False
            row = "<delay-slot>"
            mnemonic = "<delay-slot>"
        if mnemonic in arch.branch_likely_instructions:
            skip_next = True
        row = re.sub(arch.re_reg, "<reg>", row)
        row = re.sub(arch.re_sprel, "addr(sp)", row)
        row_with_imm = row
        if mnemonic in arch.instructions_with_address_immediates:
            row = row.strip()
            row, _ = split_off_branch(row)
            row += "<imm>"
        else:
            row = normalize_imms(row, arch)

        branch_target = None
        if mnemonic in arch.branch_instructions:
            target = int(row_parts[1].strip().split(",")[-1], 16)
            if mnemonic in arch.branch_likely_instructions:
                target -= 4
            branch_target = hex(target)[2:]

        output.append(
            Line(
                mnemonic=mnemonic,
                diff_row=row,
                original=original,
                normalized_original=normalized_original,
                line_num=line_num,
                branch_target=branch_target,
                source_lines=source_lines,
                comment=comment,
            )
        )
        source_lines = []

        if config.stop_jrra and mnemonic == "jr" and row_parts[1].strip() == "ra":
            stop_after_delay_slot = True
        elif stop_after_delay_slot:
            break

    return output


def normalize_imms(row: str, arch: ArchSettings) -> str:
    return re.sub(arch.re_imm, "<imm>", row)


def normalize_stack(row: str, arch: ArchSettings) -> str:
    return re.sub(arch.re_sprel, "addr(sp)", row)


def split_off_branch(line: str) -> Tuple[str, str]:
    parts = line.split(",")
    if len(parts) < 2:
        parts = line.split(None, 1)
    off = len(line) - len(parts[-1])
    return line[:off], line[off:]


def diff_sequences_difflib(
    seq1: List[str], seq2: List[str]
) -> List[Tuple[str, int, int, int, int]]:
    differ = difflib.SequenceMatcher(a=seq1, b=seq2, autojunk=False)
    return differ.get_opcodes()


def diff_sequences(
    seq1: List[str], seq2: List[str], algorithm: str
) -> List[Tuple[str, int, int, int, int]]:
    if (
        algorithm != "levenshtein"
        or len(seq1) * len(seq2) > 4 * 10 ** 8
        or len(seq1) + len(seq2) >= 0x110000
    ):
        return diff_sequences_difflib(seq1, seq2)

    # The Levenshtein library assumes that we compare strings, not lists. Convert.
    # (Per the check above we know we have fewer than 0x110000 unique elements, so chr() works.)
    remapping: Dict[str, str] = {}

    def remap(seq: List[str]) -> str:
        seq = seq[:]
        for i in range(len(seq)):
            val = remapping.get(seq[i])
            if val is None:
                val = chr(len(remapping))
                remapping[seq[i]] = val
            seq[i] = val
        return "".join(seq)

    rem1 = remap(seq1)
    rem2 = remap(seq2)
    import Levenshtein  # type: ignore

    return Levenshtein.opcodes(rem1, rem2)  # type: ignore


def diff_lines(
    lines1: List[Line],
    lines2: List[Line],
    algorithm: str,
) -> List[Tuple[Optional[Line], Optional[Line]]]:
    ret = []
    for (tag, i1, i2, j1, j2) in diff_sequences(
        [line.mnemonic for line in lines1],
        [line.mnemonic for line in lines2],
        algorithm,
    ):
        for line1, line2 in itertools.zip_longest(lines1[i1:i2], lines2[j1:j2]):
            if tag == "replace":
                if line1 is None:
                    tag = "insert"
                elif line2 is None:
                    tag = "delete"
            elif tag == "insert":
                assert line1 is None
            elif tag == "delete":
                assert line2 is None
            ret.append((line1, line2))

    return ret


@dataclass(frozen=True)
class OutputLine:
    base: Optional[Text] = field(compare=False)
    fmt2: Text = field(compare=False)
    key2: Optional[str]


def do_diff(basedump: str, mydump: str, config: Config) -> List[OutputLine]:
    if config.source:
        import cxxfilt  # type: ignore
    arch = config.arch
    fmt = config.formatter
    output: List[OutputLine] = []

    lines1 = process(basedump.split("\n"), config)
    lines2 = process(mydump.split("\n"), config)

    regFmt1 = reg_formatter("base-reg", 0)
    regFmt2 = reg_formatter("my-reg", 0)
    stackFmt1 = stack_formatter("base-stack", 4)
    stackFmt2 = stack_formatter("my-stack", 4)
    branchFmt1 = branch_formatter("base-branch", 0)
    branchFmt2 = branch_formatter("my-branch", 0)
    bts1: Set[str] = set()
    bts2: Set[str] = set()

    if config.show_branches:
        for (lines, btset, branchFmt) in [
            (lines1, bts1, branchFmt1),
            (lines2, bts2, branchFmt2),
        ]:
            for line in lines:
                bt = line.branch_target
                if bt is not None:
                    text = f"{bt}:"
                    btset.add(text)
                    branchFmt(text, from_line=eval_line_num(line.line_num), to_line=bt)

    for (line1, line2) in diff_lines(lines1, lines2, config.algorithm):
        line_color1 = line_color2 = sym_color = BasicFormat.NONE
        line_prefix = " "
        out1 = Text() if not line1 else Text(pad_mnemonic(line1.original))
        out2 = Text() if not line2 else Text(pad_mnemonic(line2.original))
        if line1 and line2 and line1.diff_row == line2.diff_row:
            if line1.normalized_original == line2.normalized_original:
                pass
            elif line1.diff_row == "<delay-slot>":
                out1 = out1.reformat(BasicFormat.DELAY_SLOT)
                out2 = out2.reformat(BasicFormat.DELAY_SLOT)
            else:
                mnemonic = line1.original.split()[0]
                branch1 = branch2 = Text()
                if mnemonic in arch.instructions_with_address_immediates:
                    out1, branch1 = map(Text, split_off_branch(out1.plain()))
                    out2, branch2 = map(Text, split_off_branch(out2.plain()))
                branchless1 = out1.plain()
                branchless2 = out2.plain()
                out1, out2 = format_fields(
                    arch.re_imm, out1, out2, lambda _: BasicFormat.IMMEDIATE
                )

                same_relative_target = False
                if line1.branch_target is not None and line2.branch_target is not None:
                    relative_target1 = eval_line_num(
                        line1.branch_target
                    ) - eval_line_num(line1.line_num)
                    relative_target2 = eval_line_num(
                        line2.branch_target
                    ) - eval_line_num(line2.line_num)
                    same_relative_target = relative_target1 == relative_target2

                if not same_relative_target and branch1.plain() != branch2.plain():
                    branch1 = branch1.reformat(BasicFormat.IMMEDIATE)
                    branch2 = branch2.reformat(BasicFormat.IMMEDIATE)

                out1 += branch1
                out2 += branch2
                if normalize_imms(branchless1, arch) == normalize_imms(
                    branchless2, arch
                ):
                    if not same_relative_target:
                        # only imms differences
                        sym_color = BasicFormat.IMMEDIATE
                        line_prefix = "i"
                else:
                    out1, out2 = format_fields(
                        arch.re_sprel, out1, out2, stackFmt1, stackFmt2
                    )
                    if normalize_stack(branchless1, arch) == normalize_stack(
                        branchless2, arch
                    ):
                        # only stack differences (luckily stack and imm
                        # differences can't be combined in MIPS, so we
                        # don't have to think about that case)
                        sym_color = BasicFormat.STACK
                        line_prefix = "s"
                    else:
                        # regs differences and maybe imms as well
                        out1, out2 = format_fields(
                            arch.re_reg, out1, out2, regFmt1, regFmt2
                        )
                        line_color1 = line_color2 = sym_color = BasicFormat.REGISTER
                        line_prefix = "r"
        elif line1 and line2:
            line_prefix = "|"
            line_color1 = line_color2 = sym_color = BasicFormat.DIFF_CHANGE
            out1 = out1.reformat(line_color1)
            out2 = out2.reformat(line_color2)
        elif line1:
            line_prefix = "<"
            line_color1 = sym_color = BasicFormat.DIFF_REMOVE
            out1 = out1.reformat(line_color1)
            out2 = Text()
        elif line2:
            line_prefix = ">"
            line_color2 = sym_color = BasicFormat.DIFF_ADD
            out1 = Text()
            out2 = out2.reformat(line_color2)

        if config.source and line2 and line2.comment:
            out2 += f" {line2.comment}"

        def format_part(
            out: Text,
            line: Optional[Line],
            line_color: Format,
            btset: Set[str],
            branchFmt: FormatBranchFunction,
        ) -> Optional[Text]:
            if line is None:
                return None
            in_arrow = Text("  ")
            out_arrow = Text()
            if config.show_branches:
                if line.line_num in btset:
                    in_arrow = Text("~>", branchFmt(line.line_num, is_target=True))
                if line.branch_target is not None:
                    out_arrow = " " + Text(
                        "~>", branchFmt(line.branch_target + ":", is_target=False)
                    )
            return (
                Text(line.line_num, line_color) + " " + in_arrow + " " + out + out_arrow
            )

        part1 = format_part(out1, line1, line_color1, bts1, branchFmt1)
        part2 = format_part(out2, line2, line_color2, bts2, branchFmt2)
        key2 = line2.original if line2 else None

        if line2:
            for source_line in line2.source_lines:
                line_format = BasicFormat.SOURCE_OTHER
                if config.source_old_binutils:
                    if source_line and re.fullmatch(".*\.c(?:pp)?:\d+", source_line):
                        line_format = BasicFormat.SOURCE_FILENAME
                    elif source_line and source_line.endswith("():"):
                        line_format = BasicFormat.SOURCE_FUNCTION
                        try:
                            source_line = cxxfilt.demangle(
                                source_line[:-3], external_only=False
                            )
                        except:
                            pass
                else:
                    # File names and function names
                    if source_line and source_line[0] != "│":
                        line_format = BasicFormat.SOURCE_FILENAME
                        # Function names
                        if source_line.endswith("():"):
                            line_format = BasicFormat.SOURCE_FUNCTION
                            try:
                                source_line = cxxfilt.demangle(
                                    source_line[:-3], external_only=False
                                )
                            except:
                                pass
                output.append(
                    OutputLine(
                        None,
                        "  " + Text(source_line, line_format),
                        source_line,
                    )
                )

        fmt2 = Text(line_prefix, sym_color) + " " + (part2 or Text())
        output.append(OutputLine(part1, fmt2, key2))

    return output


def chunk_diff(diff: List[OutputLine]) -> List[Union[List[OutputLine], OutputLine]]:
    cur_right: List[OutputLine] = []
    chunks: List[Union[List[OutputLine], OutputLine]] = []
    for output_line in diff:
        if output_line.base is not None:
            chunks.append(cur_right)
            chunks.append(output_line)
            cur_right = []
        else:
            cur_right.append(output_line)
    chunks.append(cur_right)
    return chunks


def format_diff(
    old_diff: List[OutputLine], new_diff: List[OutputLine], config: Config
) -> Tuple[Optional[Tuple[str, ...]], List[Tuple[str, ...]]]:
    fmt = config.formatter
    old_chunks = chunk_diff(old_diff)
    new_chunks = chunk_diff(new_diff)
    output: List[Tuple[Text, OutputLine, OutputLine]] = []
    assert len(old_chunks) == len(new_chunks), "same target"
    empty = OutputLine(Text(), Text(), None)
    for old_chunk, new_chunk in zip(old_chunks, new_chunks):
        if isinstance(old_chunk, list):
            assert isinstance(new_chunk, list)
            if not old_chunk and not new_chunk:
                # Most of the time lines sync up without insertions/deletions,
                # and there's no interdiffing to be done.
                continue
            differ = difflib.SequenceMatcher(a=old_chunk, b=new_chunk, autojunk=False)
            for (tag, i1, i2, j1, j2) in differ.get_opcodes():
                if tag in ["equal", "replace"]:
                    for i, j in zip(range(i1, i2), range(j1, j2)):
                        output.append((Text(), old_chunk[i], new_chunk[j]))
                if tag in ["insert", "replace"]:
                    for j in range(j1 + i2 - i1, j2):
                        output.append((Text(), empty, new_chunk[j]))
                if tag in ["delete", "replace"]:
                    for i in range(i1 + j2 - j1, i2):
                        output.append((Text(), old_chunk[i], empty))
        else:
            assert isinstance(new_chunk, OutputLine)
            assert new_chunk.base
            # old_chunk.base and new_chunk.base have the same text since
            # both diffs are based on the same target, but they might
            # differ in color. Use the new version.
            output.append((new_chunk.base, old_chunk, new_chunk))

    # TODO: status line, with e.g. approximate permuter score?
    header_line: Optional[Tuple[str, ...]]
    diff_lines: List[Tuple[str, ...]]
    if config.threeway:
        header_line = ("TARGET", "  CURRENT", "  PREVIOUS")
        diff_lines = [
            (
                fmt.apply(base),
                fmt.apply(new.fmt2),
                fmt.apply(old.fmt2) or "-" if old != new else "",
            )
            for (base, old, new) in output
        ]
    else:
        header_line = None
        diff_lines = [
            (fmt.apply(base), fmt.apply(new.fmt2))
            for (base, old, new) in output
            if base or new.key2 is not None
        ]
    return header_line, diff_lines


def debounced_fs_watch(
    targets: List[str],
    outq: "queue.Queue[Optional[float]]",
    config: Config,
    project: ProjectSettings,
) -> None:
    import watchdog.events  # type: ignore
    import watchdog.observers  # type: ignore

    class WatchEventHandler(watchdog.events.FileSystemEventHandler):  # type: ignore
        def __init__(
            self, queue: "queue.Queue[float]", file_targets: List[str]
        ) -> None:
            self.queue = queue
            self.file_targets = file_targets

        def on_modified(self, ev: object) -> None:
            if isinstance(ev, watchdog.events.FileModifiedEvent):
                self.changed(ev.src_path)

        def on_moved(self, ev: object) -> None:
            if isinstance(ev, watchdog.events.FileMovedEvent):
                self.changed(ev.dest_path)

        def should_notify(self, path: str) -> bool:
            for target in self.file_targets:
                if os.path.normpath(path) == target:
                    return True
            if config.make and any(
                path.endswith(suffix) for suffix in project.source_extensions
            ):
                return True
            return False

        def changed(self, path: str) -> None:
            if self.should_notify(path):
                self.queue.put(time.time())

    def debounce_thread() -> NoReturn:
        listenq: "queue.Queue[float]" = queue.Queue()
        file_targets: List[str] = []
        event_handler = WatchEventHandler(listenq, file_targets)
        observer = watchdog.observers.Observer()
        observed = set()
        for target in targets:
            if os.path.isdir(target):
                observer.schedule(event_handler, target, recursive=True)
            else:
                file_targets.append(os.path.normpath(target))
                target = os.path.dirname(target) or "."
                if target not in observed:
                    observed.add(target)
                    observer.schedule(event_handler, target)
        observer.start()
        while True:
            t = listenq.get()
            more = True
            while more:
                delay = t + DEBOUNCE_DELAY - time.time()
                if delay > 0:
                    time.sleep(delay)
                # consume entire queue
                more = False
                try:
                    while True:
                        t = listenq.get(block=False)
                        more = True
                except queue.Empty:
                    pass
            outq.put(t)

    th = threading.Thread(target=debounce_thread, daemon=True)
    th.start()


class Display(abc.ABC):
    basedump: str
    mydump: str
    config: Config
    emsg: Optional[str]
    last_diff_output: Optional[List[OutputLine]]

    def __init__(self, basedump: str, mydump: str, config: Config) -> None:
        self.config = config
        self.basedump = basedump
        self.mydump = mydump
        self.emsg = None
        self.last_diff_output = None

    def run_diff(self) -> str:
        if self.emsg is not None:
            return self.emsg

        diff_output = do_diff(self.basedump, self.mydump, self.config)
        last_diff_output = self.last_diff_output or diff_output
        if self.config.threeway != "base" or not self.last_diff_output:
            self.last_diff_output = diff_output
        header, diff_lines = format_diff(last_diff_output, diff_output, self.config)
        return self.config.formatter.table(header, diff_lines[self.config.skip_lines :])

    @abc.abstractmethod
    def run_sync(self) -> None:
        """Run in blocking mode, returning when the display ends"""
        ...

    @abc.abstractmethod
    def run_async(self, watch_queue: "queue.Queue[Optional[float]]") -> None:
        """Run in non-blocking mode (the method should set up the display asynchronously, then return).
        `watch_queue` should be sent `None` when the display ends"""
        ...

    @abc.abstractmethod
    def progress(self, msg: str) -> None:
        """Print a progress message (when running async)"""
        ...

    @abc.abstractmethod
    def update(self, mydump: str) -> None:
        """Update the source to be displayed (when running async)"""
        ...

    @abc.abstractmethod
    def update_error(self, error: str) -> None:
        """Display an error that occured while updating the source (when running async)"""
        ...

    @abc.abstractmethod
    def terminate(self) -> None:
        """Stop the display (when running async)"""
        ...


class PagerDisplay(Display):
    pending_update: Optional[Tuple[str, bool]]
    ready_queue: "queue.Queue[None]"
    watch_queue: "queue.Queue[Optional[float]]"
    less_proc: "Optional[subprocess.Popen[bytes]]"

    def run_less(self) -> "Tuple[subprocess.Popen[bytes], subprocess.Popen[bytes]]":
        output = self.run_diff()

        # Pipe the output through 'tail' and only then to less, to ensure the
        # write call doesn't block. ('tail' has to buffer all its input before
        # it starts writing.) This also means we don't have to deal with pipe
        # closure errors.
        buffer_proc = subprocess.Popen(
            BUFFER_CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )
        less_proc = subprocess.Popen(LESS_CMD, stdin=buffer_proc.stdout)
        assert buffer_proc.stdin
        assert buffer_proc.stdout
        buffer_proc.stdin.write(output.encode())
        buffer_proc.stdin.close()
        buffer_proc.stdout.close()
        return (buffer_proc, less_proc)

    def kill_less(self) -> None:
        if not self.less_proc:
            return
        self.less_proc.kill()
        self.ready_queue.get()

    def run_sync(self) -> None:
        proca, procb = self.run_less()
        procb.wait()
        proca.wait()

    def run_async(self, watch_queue: "queue.Queue[Optional[float]]") -> None:
        self.watch_queue = watch_queue
        self.ready_queue = queue.Queue()
        self.pending_update = None
        dthread = threading.Thread(target=self.display_thread)
        dthread.start()
        self.ready_queue.get()

    def display_thread(self) -> None:
        proca, procb = self.run_less()
        self.less_proc = procb
        self.ready_queue.put(None)
        while True:
            ret = procb.wait()
            proca.wait()
            self.less_proc = None
            if ret != 0:
                # fix the terminal
                os.system("tput reset")
            if ret != 0 and self.pending_update is not None:
                # killed by program with the intent to refresh
                msg, error = self.pending_update
                self.pending_update = None
                if not error:
                    self.mydump = msg
                    self.emsg = None
                else:
                    self.emsg = msg
                proca, procb = self.run_less()
                self.less_proc = procb
                self.ready_queue.put(None)
            else:
                # terminated by user, or killed
                self.watch_queue.put(None)
                self.ready_queue.put(None)
                break

    def progress(self, msg: str) -> None:
        # Write message to top-left corner
        sys.stdout.write("\x1b7\x1b[1;1f{}\x1b8".format(msg + " "))
        sys.stdout.flush()

    def update(self, mydump: str) -> None:
        if not self.emsg and mydump == self.mydump:
            self.progress("Unchanged. ")
            return
        self.pending_update = (mydump, False)
        self.kill_less()

    def update_error(self, error: str) -> None:
        self.pending_update = (error, True)
        self.kill_less()

    def terminate(self) -> None:
        self.pending_update = None
        self.kill_less()


class WebDisplay(Display):
    watch_queue: "queue.Queue[Optional[float]]"
    ready_queue: "queue.Queue[Optional[float]]"
    status_queue: "queue.Queue[str]"
    http_server: http.server.HTTPServer
    running_async: bool
    running: bool

    def open_browser(self, once: bool = False) -> None:
        if self.config.run_browser:
            env_browser_command = os.environ.get("ASMDW_BROWSER_CMD")
            if env_browser_command:
                os.system(
                    env_browser_command.format(query="init&" + ("once" if once else ""))
                )
            else:
                import webbrowser

                webbrowser.open(self.get_open_url(once))

    def get_open_url(self, once: bool = False) -> str:
        port = self.config.http_server_port
        return f"http://localhost:{port}?init&" + ("once" if once else "")

    def handle_request(self, req: http.server.BaseHTTPRequestHandler) -> None:
        if not self.running:
            return

        def badRequest(msg: str) -> None:
            req.send_response(http.HTTPStatus.BAD_REQUEST)
            req.send_header("Content-Type", "text/plain; charset=UTF-8")
            req.end_headers()
            req.wfile.write(msg.encode("utf-8"))
            req.wfile.flush()

        # scheme://netloc/path;parameters?query#fragment
        scheme, netloc, path, parameters, query_str, fragment = urllib.parse.urlparse(
            req.path
        )
        if not query_str:
            badRequest(
                "No query\n" + f"path = {path!r}\n" + f"query_str = {query_str!r}\n"
            )
            return
        query = urllib.parse.parse_qs(query_str, keep_blank_values=True)
        if "init" in query:
            # serve client.html
            req.send_response(http.HTTPStatus.OK)
            req.send_header("Content-Type", "text/html; charset=UTF-8")
            req.end_headers()
            with open("client.html") as f:
                req.wfile.write(f.read().encode("utf-8"))
            req.wfile.flush()
        elif "css" in query:
            # serve diff-stylesheet.css
            req.send_response(http.HTTPStatus.OK)
            req.send_header("Content-Type", "text/css; charset=UTF-8")
            req.end_headers()
            with open("diff-stylesheet.css") as f:
                req.wfile.write(f.read().encode("utf-8"))
            req.wfile.flush()
        elif "diff" in query:
            # serve diff or status message
            if self.running_async:
                if "nowait" in query:
                    try:
                        # take from the queue just in case if any, to prevent
                        # following ?diff request to complete immediately
                        self.ready_queue.get_nowait()
                    except queue.Empty:
                        pass
                else:
                    self.ready_queue.get()
                    if not self.running:
                        # notify any other request waiting
                        self.ready_queue.put(None)
                        return
            req.send_response(http.HTTPStatus.OK)
            req.send_header("Content-Type", "text/plain; charset=UTF-8")
            req.end_headers()
            if self.running_async:
                try:
                    status = self.status_queue.get_nowait()
                except queue.Empty:
                    status = None
            else:
                status = None
            if status:
                req.wfile.write("status\n".encode("utf-8"))
                req.wfile.write(status.encode("utf-8"))
            else:
                req.wfile.write("diff\n".encode("utf-8"))
                req.wfile.write(self.run_diff().encode("utf-8"))
            req.wfile.flush()
        else:
            badRequest("Bad query")

    def run_server(self, run_async: bool) -> None:
        class WebDisplayRequestHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(req) -> None:
                self.handle_request(req)

            def log_request(
                req,
                code: Union[str, http.HTTPStatus] = "-",
                size: Union[str, int] = "-",
            ) -> None:
                if self.config.log_http_requests:
                    super().log_request(code, size)

        # NB: Using ThreadingHTTPServer is said to prevent streaming
        # it probably won't be an issue in this application
        try:
            ThreadingHTTPServer = http.server.ThreadingHTTPServer
        except:
            import socketserver

            class ThreadingHTTPServer(
                socketserver.ThreadingMixIn, http.server.HTTPServer
            ):
                pass

        self.http_server = ThreadingHTTPServer(
            ("localhost", self.config.http_server_port), WebDisplayRequestHandler
        )
        self.running_async = run_async
        self.running = True
        print(self.get_open_url(not run_async))
        # opening the browser before the server is started
        # hope it won't be an issue
        self.open_browser(once=not run_async)
        if run_async:
            threading.Thread(target=self.http_server.serve_forever).start()
        else:
            self.http_server.serve_forever()

    def run_sync(self) -> None:
        self.run_server(False)

    def run_async(self, watch_queue: "queue.Queue[Optional[float]]") -> None:
        self.watch_queue = watch_queue
        self.ready_queue = queue.Queue()
        self.status_queue = queue.Queue()
        self.run_server(True)

    def progress(self, msg: str) -> None:
        self.status_queue.put(msg)
        self.ready_queue.put(None)

    def update(self, mydump: str) -> None:
        if mydump == self.mydump:
            self.progress("Unchanged. ")
            return
        self.mydump = mydump
        self.ready_queue.put(None)

    def update_error(self, error: str) -> None:
        self.status_queue.put(f"Error: {error}")
        self.ready_queue.put(None)

    def terminate(self) -> None:
        self.running = False
        self.ready_queue.put(None)
        self.http_server.shutdown()


class ConsoleDisplay(Display):
    def print_diff(self) -> None:
        print(self.run_diff())

    def run_sync(self) -> None:
        self.print_diff()

    def run_async(self, watch_queue: "queue.Queue[Optional[float]]") -> None:
        self.print_diff()

    def progress(self, msg: str) -> None:
        print(msg)

    def update(self, mydump: str) -> None:
        if mydump == self.mydump:
            self.progress("Unchanged. ")
            return
        self.mydump = mydump
        self.print_diff()

    def update_error(self, error: str) -> None:
        print("Error:")
        print(error)

    def terminate(self) -> None:
        pass


def main() -> None:
    args = parser.parse_args()

    # Apply project-specific configuration.
    settings: Dict[str, Any] = {}
    diff_settings.apply(settings, args)  # type: ignore
    project = create_project_settings(settings)

    config = create_config(args, project)

    if config.algorithm == "levenshtein":
        try:
            import Levenshtein
        except ModuleNotFoundError as e:
            fail(MISSING_PREREQUISITES.format(e.name))

    if config.source:
        try:
            import cxxfilt
        except ModuleNotFoundError as e:
            fail(MISSING_PREREQUISITES.format(e.name))

    if config.threeway and not args.watch:
        fail("Threeway diffing requires -w.")

    if args.diff_elf_symbol:
        make_target, basecmd, mycmd = dump_elf(
            args.start, args.end, args.diff_elf_symbol, config, project
        )
    elif config.diff_obj:
        make_target, basecmd, mycmd = dump_objfile(
            args.start, args.end, config, project
        )
    else:
        make_target, basecmd, mycmd = dump_binary(args.start, args.end, config, project)

    map_build_target_fn = getattr(diff_settings, "map_build_target", None)
    if map_build_target_fn:
        make_target = map_build_target_fn(make_target=make_target)

    if args.write_asm is not None:
        mydump = run_objdump(mycmd, config, project)
        with open(args.write_asm, "w") as f:
            f.write(mydump)
        print(f"Wrote assembly to {args.write_asm}.")
        sys.exit(0)

    if args.base_asm is not None:
        with open(args.base_asm) as f:
            basedump = f.read()
    else:
        basedump = run_objdump(basecmd, config, project)

    mydump = run_objdump(mycmd, config, project)

    if config.use_pager:
        display = PagerDisplay(basedump, mydump, config)
    elif config.web_server:
        display = WebDisplay(basedump, mydump, config)
    else:
        display = ConsoleDisplay(basedump, mydump, config)

    if not args.watch:
        display.run_sync()
    else:
        if not args.make and not args.no_make:
            yn = input(
                "Warning: watch-mode (-w) enabled without auto-make (-m). "
                "You will have to run make manually. Ok? (Y/n) "
            )
            if yn.lower() == "n":
                return
        if args.make:
            watch_sources = None
            watch_sources_for_target_fn = getattr(
                diff_settings, "watch_sources_for_target", None
            )
            if watch_sources_for_target_fn:
                watch_sources = watch_sources_for_target_fn(make_target)
            watch_sources = watch_sources or project.source_directories
            if not watch_sources:
                fail("Missing source_directories config, don't know what to watch.")
        else:
            watch_sources = [make_target]
        q: "queue.Queue[Optional[float]]" = queue.Queue()
        debounced_fs_watch(watch_sources, q, config, project)
        display.run_async(q)
        last_build = 0.0
        try:
            while True:
                t = q.get()
                if t is None:
                    break
                if t < last_build:
                    continue
                last_build = time.time()
                if args.make:
                    display.progress("Building...")
                    ret = run_make_capture_output(make_target, project)
                    if ret.returncode != 0:
                        display.update_error(
                            ret.stderr.decode("utf-8-sig", "replace")
                            or ret.stdout.decode("utf-8-sig", "replace"),
                        )
                        continue
                mydump = run_objdump(mycmd, config, project)
                display.update(mydump)
        except KeyboardInterrupt:
            print(" Terminating display...")
            display.terminate()


if __name__ == "__main__":
    main()
