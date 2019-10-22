#!/usr/bin/env python3
import sys
import re
import os
import ast
import argparse
import subprocess
import difflib
import string
import itertools

def fail(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)

try:
    import attr
    from colorama import Fore, Style, Back
    import ansiwrap
except ModuleNotFoundError as e:
    fail(f"Missing prerequisite python module {e.name}. "
        "Run `python3 -m pip install --user colorama ansiwrap attrs` to install prerequisites.")

# Prefer to use diff_settings.py from the current working directory
sys.path.insert(0, '.')
try:
    import diff_settings
except ModuleNotFoundError:
    fail("Unable to find diff_settings.py in the same directory.")

# ==== CONFIG ====

parser = argparse.ArgumentParser(
        description="Diff mips assembly")
parser.add_argument('start',
        help="Function name or address to start diffing from.")
parser.add_argument('end', nargs='?',
        help="Address to end diff at.")
parser.add_argument('-o', dest='diff_obj', action='store_true',
        help="Diff .o files rather than a whole binary. This makes it possible to see symbol names.")
parser.add_argument('--base-asm', dest='base_asm',
        help="Read assembly from given file instead of configured base img.")
parser.add_argument('--write-asm', dest='write_asm',
        help="Write the current assembly output to file, e.g. for use with --base-asm.")
parser.add_argument('-m', '--make', dest='make', action='store_true',
        help="Automatically run 'make' on the .o file or binary before diffing.")
parser.add_argument('-l', '--skip-lines', dest='skip_lines', type=int, default=0,
        help="Skip the first N lines of output.")
parser.add_argument('-s', '--stop-jr-ra', dest='stop_jrra', action='store_true',
        help="Stop disassembling at the first 'jr ra'. Some functions have multiple return points, so use with care!")
parser.add_argument('-i', '--ignore-large-imms', dest='ignore_large_imms', action='store_true',
        help="Pretend all large enough immediates are the same.")
parser.add_argument('-S', '--base-shift', dest='base_shift', type=str, default='0',
        help="Diff position X in our img against position X + shift in the base img. "
        "Arithmetic is allowed, so e.g. |-S \"0x1234 - 0x4321\"| is a reasonable "
        "flag to pass if it is known that position 0x1234 in the base img syncs "
        "up with position 0x4321 in our img. Not supported together with -o.")
parser.add_argument('--width', dest='column_width', type=int, default=50,
        help="Sets the width of the left and right view column.")

# Project-specific flags, e.g. different versions/make arguments.
if hasattr(diff_settings, "add_custom_arguments"):
    diff_settings.add_custom_arguments(parser)

args = parser.parse_args()

# Set imgs, map file and make flags in a project-specific manner.
config = {}
diff_settings.apply(config, args)

baseimg = config['baseimg']
myimg = config['myimg']
mapfile = config.get('mapfile', None)
makeflags = config.get('makeflags', [])

MAX_FUNCTION_SIZE_LINES = 1024
MAX_FUNCTION_SIZE_BYTES = 1024 * 4

COLOR_ROTATION = [
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

# ==== LOGIC ====

binutils_prefix = None

for binutils_cand in ['mips-linux-gnu-', 'mips64-elf-']:
    try:
        subprocess.check_call([binutils_cand + "objdump", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        binutils_prefix = binutils_cand
        break
    except subprocess.CalledProcessError:
        pass

if not binutils_prefix:
    fail("Missing binutils; please ensure mips-linux-gnu-objdump or mips64-elf-objdump exist.")

def run_make(target):
    subprocess.check_call(["make"] + makeflags + [target])

def run_objdump(flags, target):
    return subprocess.check_output([binutils_prefix + "objdump"] + flags + [target], universal_newlines=True)

def eval_int(expr, emsg=None):
    try:
        ret = ast.literal_eval(expr)
        if not isinstance(ret, int):
            raise Exception("not an integer")
        return ret
    except Exception:
        if emsg is not None:
            fail(emsg)
        return None

base_shift = eval_int(args.base_shift, "Failed to parse --base-shift (-S) argument as an integer.")

def restrict_to_function(dump, fn_name):
    out = []
    search = f'<{fn_name}>:'
    found = False
    for line in dump.split('\n'):
        if found:
            if len(out) >= MAX_FUNCTION_SIZE_LINES:
                break
            out.append(line)
        elif search in line:
            found = True
    return '\n'.join(out)

def search_map_file(fn_name):
    if not mapfile:
        fail(f"No map file configured; cannot find function {fn_name}.")

    try:
        with open(mapfile) as f:
            lines = f.read().split('\n')
    except Exception:
        fail(f"Failed to open map file {mapfile} for reading.")

    try:
        cur_objfile = None
        ram_to_rom = None
        cands = []
        last_line = ''
        for line in lines:
            if line.startswith(' .text'):
                cur_objfile = line.split()[3]
            if 'load address' in line:
                tokens = last_line.split() + line.split()
                ram = int(tokens[1], 0)
                rom = int(tokens[5], 0)
                ram_to_rom = rom - ram
            if line.endswith(' ' + fn_name):
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
    return None, None

def dump_objfile():
    if base_shift:
        fail("--base-shift not compatible with -o")
    if args.end is not None:
        fail("end address not supported together with -o")
    if args.start.startswith('0'):
        fail("numerical start address not supported with -o; pass a function name")

    objfile, _ = search_map_file(args.start)
    if not objfile:
        fail("Not able to find .o file for function.")

    if args.make:
        run_make(objfile)

    if not os.path.isfile(objfile):
        fail("Not able to find .o file for function.")

    refobjfile = "expected/" + objfile
    if not os.path.isfile(refobjfile):
        fail(f'Please ensure an OK .o file exists at "{refobjfile}".')

    objdump_flags = ["-drz"]
    if args.base_asm is None:
        basedump = run_objdump(objdump_flags, refobjfile)
        basedump = restrict_to_function(basedump, args.start)
    mydump = run_objdump(objdump_flags, objfile)
    mydump = restrict_to_function(mydump, args.start)
    return basedump, mydump

def dump_binary():
    if args.make:
        run_make(myimg)
    start_addr = eval_int(args.start)
    if start_addr is None:
        _, start_addr = search_map_file(args.start)
        if start_addr is None:
            fail("Not able to find function in map file.")
    if args.end is not None:
        end_addr = eval_int(args.end, "End address must be an integer expression.")
    else:
        end_addr = start_addr + MAX_FUNCTION_SIZE_BYTES
    objdump_flags = ['-Dz', '-bbinary', '-mmips', '-EB']
    flags1 = [f"--start-address={start_addr + base_shift}", f"--stop-address={end_addr + base_shift}"]
    flags2 = [f"--start-address={start_addr}", f"--stop-address={end_addr}"]
    if args.base_asm is None:
        basedump = run_objdump(objdump_flags + flags1, baseimg)
    mydump = run_objdump(objdump_flags + flags2, myimg)
    return basedump, mydump

# Alignment with ANSI colors is broken, let's fix it.
def ansi_ljust(s, width):
    needed = width - ansiwrap.ansilen(s)
    if needed > 0:
        return s + ' ' * needed
    else:
        return s

re_int = re.compile(r'[0-9]+')
re_comments = re.compile(r'<.*?>')
re_regs = re.compile(r'\b(a[0-3]|t[0-9]|s[0-7]|at|v[01]|f[12]?[0-9]|f3[01]|fp)\b')
re_sprel = re.compile(r',([1-9][0-9]*|0x[1-9a-f][0-9a-f]*)\(sp\)')
re_large_imm = re.compile(r'-?[1-9][0-9]{2,}|-?0x[0-9a-f]{3,}')
forbidden = set(string.ascii_letters + '_')
branch_likely_instructions = [
    'beql', 'bnel', 'beqzl', 'bnezl', 'bgezl', 'bgtzl', 'blezl', 'bltzl',
    'bc1tl', 'bc1fl'
]
branch_instructions = [
    'b', 'beq', 'bne', 'beqz', 'bnez', 'bgez', 'bgtz', 'blez', 'bltz',
    'bc1t', 'bc1f'
] + branch_likely_instructions

def hexify_int(row, pat):
    full = pat.group(0)
    if len(full) <= 1:
        # leave one-digit ints alone
        return full
    start, end = pat.span()
    if start and row[start - 1] in forbidden:
        return full
    if end < len(row) and row[end] in forbidden:
        return full
    return hex(int(full))

def parse_relocated_line(line):
    try:
        ind2 = line.rindex(',')
    except ValueError:
        ind2 = line.rindex('\t')
    before = line[:ind2+1]
    after = line[ind2+1:]
    ind2 = after.find('(')
    if ind2 == -1:
        imm, after = after, ''
    else:
        imm, after = after[:ind2], after[ind2:]
    if imm == '0x0':
        imm = '0'
    return before, imm, after

def process_reloc(row, prev):
    before, imm, after = parse_relocated_line(prev)
    repl = row.split()[-1]
    if imm != '0':
        if before.strip() == 'jal' and not imm.startswith('0x'):
            imm = '0x' + imm
        repl += '+' + imm if int(imm,0) > 0 else imm
    if 'R_MIPS_LO16' in row:
        repl = f'%lo({repl})'
    elif 'R_MIPS_HI16' in row:
        # Ideally we'd pair up R_MIPS_LO16 and R_MIPS_HI16 to generate a
        # correct addend for each, but objdump doesn't give us the order of
        # the relocations, so we can't find the right LO16. :(
        repl = f'%hi({repl})'
    else:
        assert 'R_MIPS_26' in row, f"unknown relocation type '{row}'"
    return before + repl + after

def process(lines):
    diff_rows = []
    skip_next = False
    originals = []
    line_nums = []
    if not args.diff_obj:
        lines = lines[7:]
        if lines and not lines[-1]:
            lines.pop()

    for row in lines:
        if args.diff_obj and ('>:' in row or not row):
            continue

        if 'R_MIPS_' in row:
            if diff_rows[-1] != '<skipped>':
                diff_rows[-1] = process_reloc(row, diff_rows[-1])
            originals[-1] = process_reloc(row, originals[-1])
            continue

        row = re.sub(re_comments, '', row)
        row = row.rstrip()
        tabs = row.split('\t')
        row = '\t'.join(tabs[2:])
        line_num = tabs[0].strip()
        mnemonic = row.split('\t')[0].strip()
        if mnemonic not in branch_instructions:
            row = re.sub(re_int, lambda s: hexify_int(row, s), row)
        original = row
        if skip_next:
            skip_next = False
            row = '<skipped>'
        if mnemonic in branch_likely_instructions:
            skip_next = True
        row = re.sub(re_regs, '<reg>', row)
        row = re.sub(re_sprel, ',addr(sp)', row)
        if args.ignore_large_imms:
            row = re.sub(re_large_imm, '<imm>', row)

        # Replace tabs with spaces
        diff_rows.append(row)
        originals.append(original)
        line_nums.append(line_num)
        if args.stop_jrra and mnemonic == 'jr' and row.split('\t')[1].strip() == 'ra':
            break

    # Cleanup whitespace
    originals = [original.strip() for original in originals]
    originals = [''.join(f'{o:<8s}' for o in original.split('\t')) for original in originals]
    # return diff_rows, diff_rows, line_nums
    return diff_rows, originals, line_nums

def format_single_line_diff(line1, line2, column_width):
    return f"{ansi_ljust(line1,column_width)}{ansi_ljust(line2,column_width)}"

class SymbolColorer:
    def __init__(self, base_index):
        self.color_index = base_index
        self.symbol_colors = {}

    def color_symbol(self, s):
        s = s.group()
        try:
            color = self.symbol_colors[s]
        except:
            color = COLOR_ROTATION[self.color_index % len(COLOR_ROTATION)]
            self.color_index += 1
            self.symbol_colors[s] = color
        return f'{color}{s}{Fore.RESET}'

def norm(row):
    if args.ignore_large_imms:
        row = re.sub(re_large_imm, '<imm>', row)
    return row

def run(basedump, mydump):
    asm1_lines = basedump.split('\n')
    asm2_lines = mydump.split('\n')

    output = []

    asm1_lines, originals1, line_nums1 = process(asm1_lines)
    asm2_lines, originals2, line_nums2 = process(asm2_lines)

    sc1 = SymbolColorer(0)
    sc2 = SymbolColorer(0)
    sc3 = SymbolColorer(4)
    sc4 = SymbolColorer(4)

    differ: difflib.SequenceMatcher = difflib.SequenceMatcher(a=asm1_lines, b=asm2_lines, autojunk=True)
    for (tag, i1, i2, j1, j2) in differ.get_opcodes():
        lines1 = asm1_lines[i1:i2]
        lines2 = asm2_lines[j1:j2]

        for k, (line1, line2) in enumerate(itertools.zip_longest(lines1, lines2)):
            if tag == 'replace':
                if line1 == None:
                    tag = 'insert'
                elif line2 == None:
                    tag = 'delete'

            try:
                original1 = originals1[i1+k]
                line_num1 = line_nums1[i1+k]
            except:
                original1 = ''
                line_num1 = ''
            try:
                original2 = originals2[j1+k]
                line_num2 = line_nums2[j1+k]
            except:
                original2 = ''
                line_num2 = ''

            line_color = Fore.RESET
            line_prefix = ' '
            if tag == 'equal' or line1 == line2:
                if line1 == '<skipped>' and norm(original1) != norm(original2):
                    line1 = f'{Style.DIM}{original1}'
                    line2 = f'{Style.DIM}{original2}'
                elif norm(original1) != norm(original2):
                    line_color = Fore.YELLOW
                    line_prefix = 'r'
                    line1 = f'{Fore.YELLOW}{original1}{Style.RESET_ALL}'
                    line2 = f'{Fore.YELLOW}{original2}{Style.RESET_ALL}'
                    line1 = re.sub(re_regs, lambda s: sc1.color_symbol(s), line1)
                    line2 = re.sub(re_regs, lambda s: sc2.color_symbol(s), line2)
                    line1 = re.sub(re_sprel, lambda s: sc3.color_symbol(s), line1)
                    line2 = re.sub(re_sprel, lambda s: sc4.color_symbol(s), line2)
                else:
                    line1 = f'{original1}'
                    line2 = f'{original2}'
            elif tag == 'replace':
                line_prefix = '|'
                line_color = Fore.BLUE
                line1 = f"{Fore.BLUE}{original1}{Style.RESET_ALL}"
                line2 = f"{Fore.BLUE}{original2}{Style.RESET_ALL}"
            elif tag == 'delete':
                line_prefix = '<'
                line_color = Fore.RED
                line1 = f"{Fore.RED}{original1}{Style.RESET_ALL}"
            elif tag == 'insert':
                line_prefix = '>'
                line_color = Fore.GREEN
                line2 = f"{Fore.GREEN}{original2}{Style.RESET_ALL}"

            line1 = line1 or ''
            line2 = line2 or ''

            line_num1 = line_num1 if line1 else ''
            line_num2 = line_num2 if line2 else ''

            line1 =               f"{line_color}{line_num1}    {line1}{Style.RESET_ALL}"
            line2 = f"{line_color}{line_prefix} {line_num2}    {line2}{Style.RESET_ALL}"
            output.append(format_single_line_diff(line1, line2, args.column_width))

    return output[args.skip_lines:]


def main():
    if args.diff_obj:
        basedump, mydump = dump_objfile()
    else:
        basedump, mydump = dump_binary()

    if args.write_asm is not None:
        with open(args.write_asm) as f:
            f.write(mydump)
        print(f"Wrote assembly to {args.write_asm}.")
        sys.exit(0)

    if args.base_asm is not None:
        with open(args.base_asm) as f:
            basedump = f.read()

    output = '\n'.join(run(basedump, mydump))
    # output = sha1sum(mydump) + '\n' + output

    subprocess.run(["less", "-Ric"], input=output.encode('utf-8'))

main()
