#!/usr/bin/env bash

set -e

# ==== CONFIG ====

DIFF_OBJ=0
IGNORE_REGS=0

POSITIONAL=()
while [[ $# -gt 0 ]]; do
case "$1" in
    -o)
        DIFF_OBJ=1
        shift
        ;;
    -r)
        IGNORE_REGS=1
        shift
        ;;
    *)
        POSITIONAL+=("$1")
        shift
        ;;
esac
done
set -- "${POSITIONAL[@]}"

# Set $BASEIMG, $BASEDUMP, $MYIMP, $MYDUMP, $MAPFILE in a project-specific manner.
. diff-settings.sh

# ==== LOGIC ====

if [[ $# -lt 1 ]]; then
    echo "Usage: ./diff.sh [flags] (function|rom addr) [end rom addr]" >&2
    exit 1
fi

START="$1"
BASE=0

set +e

if [ -n "$MAPFILE" ]; then
    LINE=$(grep "$1$" $MAPFILE)
    if [[ -n "$LINE" && "${1:0:2}" != "0x" ]]; then
        START=$(echo $LINE | cut -d' ' -f1)
        if [[ $DIFF_OBJ = 1 ]]; then
            LINE2=$(grep "$1$\|^ .text" $MAPFILE | grep "$1$" -B1 | head -n1)
            OBJFILE=$(echo $LINE2 | cut -d' ' -f4)
        else
            LINE2=$(grep "$1$\|load address" $MAPFILE | grep "$1$" -B1 | head -n1)
            RAM=$(echo $LINE2 | cut -d' ' -f2)
            ROM=$(echo $LINE2 | cut -d' ' -f6)
            BASE="$RAM - $ROM"
        fi
    fi
fi

read -r -d '' TRANSFORM_SCRIPT << EOM
import sys
import re
import string
import traceback

# Ignore registers, for cleaner output.
ign_regs = sys.argv[1] == '1'

# Diff .o files rather than whole binaries.
diff_obj = sys.argv[2] == '1'

# Skip branch-likely delay slots. (They aren't interesting on IDO.)
skip_bl_delay_slots = True

r = re.compile(r'[0-9]+')
comments = re.compile(r'<.*?>')
regs = re.compile(r'\b(a[0-3]|t[0-9]|s[0-7]|at|v[01])\b')
sprel = re.compile(r',([1-9][0-9]*|0x[1-9a-f][0-9a-f]*)\(sp\)')
forbidden = set(string.ascii_letters + '_')
skip_lines = 1 if diff_obj else 7
branch_likely_instructions = [
    'beql', 'bnel', 'beqzl', 'bnezl', 'bgezl', 'bgtzl', 'blezl', 'bltzl',
    'bc1tl', 'bc1fl'
]
branch_instructions = [
    'b', 'beq', 'bne', 'beqz', 'bnez', 'bgez', 'bgtz', 'blez', 'bltz',
    'bc1t', 'bc1f'
] + branch_likely_instructions

def fn(pat):
    full = pat.group(0)
    if len(full) <= 1:
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

output = []
skip_next = False
for index, row in enumerate(sys.stdin):
    if index < skip_lines:
        continue
    try:
        row = row.rstrip()
        if diff_obj and ('>:' in row or not row):
            continue
        if 'R_MIPS_' in row:
            prev = output[-1]
            if prev == '<skipped>':
                continue
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
            output[-1] = before + repl + after
            continue
        row = re.sub(comments, '', row)
        row = row.rstrip()
        row = '\t'.join(row.split('\t')[2:]) # [20:]
        mnemonic = row.split('\t')[0].strip()
        if mnemonic not in branch_instructions:
            row = re.sub(r, fn, row)
        if skip_next:
            skip_next = False
            row = '<skipped>'
        if mnemonic in branch_likely_instructions and skip_bl_delay_slots:
            skip_next = True
        if ign_regs:
            row = re.sub(regs, '<reg>', row)
            row = re.sub(sprel, ',addr(sp)', row)
        # row = row.replace(',', ', ')
        output.append(row)
    except Exception as e:
        print(f"failed to parse line: {row}", file=sys.stderr)
        traceback.print_exc()
        break

for row in output:
    print(row)
EOM

set -e

TRANSFORM=(python3 -c "$TRANSFORM_SCRIPT" $IGNORE_REGS $DIFF_OBJ)

if [[ $DIFF_OBJ = 1 ]]; then
    if [[ ! -f "$OBJFILE" ]]; then
        echo Not able to find .o file for function.
        exit 1
    fi
    REFOBJFILE="expected/$OBJFILE"
    if [[ ! -f "$REFOBJFILE" ]]; then
        echo Please ensure an OK .o file exists at "$REFOBJFILE".
        exit 1
    fi
    OBJDUMP="mips-linux-gnu-objdump -drz"
    $OBJDUMP $REFOBJFILE | grep "<$1>:" -A1000 | "${TRANSFORM[@]}" > $BASEDUMP
    $OBJDUMP -S $OBJFILE | grep "<$1>:" -A1000 | "${TRANSFORM[@]}" > $MYDUMP
else
    END="$START + 0x1000"
    if [[ $# -ge 2 ]]; then
        END="$2"
    fi

    OBJDUMP="mips-linux-gnu-objdump -D -z -bbinary -mmips -EB"
    OPTIONS="--start-address=$(($START - ($BASE))) --stop-address=$(($END - ($BASE)))"
    $OBJDUMP $OPTIONS $BASEIMG | "${TRANSFORM[@]}" > $BASEDUMP

    NEWOPTIONS="--start-address=$(($START - ($BASE))) --stop-address=$(($END - ($BASE)))"
    $OBJDUMP $NEWOPTIONS $MYIMG | "${TRANSFORM[@]}" > $MYDUMP
fi

sed -i "1s;^;$(sha1sum $MYDUMP)\n;" $MYDUMP

# Inline word diff
wdiff -n $BASEDUMP $MYDUMP | colordiff | less

# Side by side
# diff -y $BASEDUMP $MYDUMP | colordiff | less
