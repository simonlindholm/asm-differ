import unittest
import diff
import json


class TestSh2(unittest.TestCase):
    def get_config(self) -> diff.Config:
        arch = diff.get_arch("sh2")
        formatter = diff.JsonFormatter(arch_str="sh2")
        config = diff.Config(
            arch=arch,
            diff_obj=True,
            file=None,
            ref_file=None,
            make=False,
            source_old_binutils=True,
            diff_section=".text",
            inlines=False,
            max_function_size_lines=25000,
            max_function_size_bytes=100000,
            formatter=formatter,
            diff_mode=diff.DiffMode.NORMAL,
            base_shift=0,
            skip_lines=0,
            compress=None,
            show_rodata_refs=True,
            show_branches=True,
            show_line_numbers=False,
            show_source=False,
            stop_at_ret=None,
            ignore_large_imms=False,
            ignore_addr_diffs=True,
            algorithm="levenshtein",
            reg_categories={},
            diff_function_symbols=False,
        )
        return config

    # check that comment <> regex has ? to avoid "<func_060E8780+0x44>,r1      ! 60e87d0"
    # all being a comment for:
    # mov.l   44 <func_060E8780+0x44>,r1      ! 60e87d0
    def test_sh2_comment(self) -> None:
        # parser specifically looks for tabs so make sure they are represented

        # 16:   d1 0b           mov.l   44 <func_060E8780+0x44>,r1      ! 60e87d0
        sh2_theirs = (
            "  16:\td1 0b       \tmov.l\t44 <func_060E8780+0x44>,r1\t! 60e87d0\n"
        )

        # 16:   d1 0b           mov.l   44 <_func_060E8780+0x44>,r1     ! 0 <_func_060E8780>
        sh2_ours = "  16:\td1 0b       \tmov.l\t44 <_func_060E8780+0x44>,r1\t! 0 <_func_060E8780>\n"

        config = self.get_config()
        display = diff.Display(sh2_theirs, sh2_ours, config)
        loaded = json.loads(display.run_diff()[0])

        curr = loaded["rows"][0]["current"]["src_comment"]

        assert curr != "<_func_060E8780+0x44>,r1     ! 0 <_func_060E8780>"
        assert curr == "<_func_060E8780+0x44>"

    def test_sh2_immediates(self) -> None:
        # test parsing these immediates
        # func_0606B760():
        # 0:   ec 01           mov     #1,r12
        # 2:   71 01           add     #1,r1
        # 4:   c8 01           tst     #1,r0
        # 6:   c9 01           and     #1,r0
        # 8:   cb 01           or      #1,r0
        # a:   ca 01           xor     #1,r0
        # c:   ec ff           mov     #-1,r12
        # e:   71 ff           add     #-1,r1
        # 10:   c8 ff           tst     #255,r0
        # 12:   c9 ff           and     #255,r0
        # 14:   cb ff           or      #255,r0
        # 16:   ca ff           xor     #255,r0
        # 18:   ec 7f           mov     #127,r12
        # 1a:   71 7f           add     #127,r1
        # 1c:   c8 7f           tst     #127,r0
        # 1e:   c9 7f           and     #127,r0
        # 20:   cb 7f           or      #127,r0
        # 22:   ca 7f           xor     #127,r0
        # 24:   ec 80           mov     #-128,r12
        # 26:   71 80           add     #-128,r1
        # 28:   c8 80           tst     #128,r0
        # 2a:   c9 80           and     #128,r0
        # 2c:   cb 80           or      #128,r0
        # 2e:   ca 80           xor     #128,r0
        sh2_theirs = "func_0606B760():\n   0:\tec 01       \tmov\t#1,r12\n   2:\t71 01       \tadd\t#1,r1\n   4:\tc8 01       \ttst\t#1,r0\n   6:\tc9 01       \tand\t#1,r0\n   8:\tcb 01       \tor\t#1,r0\n   a:\tca 01       \txor\t#1,r0\n   c:\tec ff       \tmov\t#-1,r12\n   e:\t71 ff       \tadd\t#-1,r1\n  10:\tc8 ff       \ttst\t#255,r0\n  12:\tc9 ff       \tand\t#255,r0\n  14:\tcb ff       \tor\t#255,r0\n  16:\tca ff       \txor\t#255,r0\n  18:\tec 7f       \tmov\t#127,r12\n  1a:\t71 7f       \tadd\t#127,r1\n  1c:\tc8 7f       \ttst\t#127,r0\n  1e:\tc9 7f       \tand\t#127,r0\n  20:\tcb 7f       \tor\t#127,r0\n  22:\tca 7f       \txor\t#127,r0\n  24:\tec 80       \tmov\t#-128,r12\n  26:\t71 80       \tadd\t#-128,r1\n  28:\tc8 80       \ttst\t#128,r0\n  2a:\tc9 80       \tand\t#128,r0\n  2c:\tcb 80       \tor\t#128,r0\n  2e:\tca 80       \txor\t#128,r0"

        # just diff with self
        sh2_ours = sh2_theirs

        config = self.get_config()
        display = diff.Display(sh2_theirs, sh2_ours, config)
        loaded = json.loads(display.run_diff()[0])

        expected = [
            "0:    mov     #0x1,r12",
            "2:    add     #0x1,r1",
            "4:    tst     #0x1,r0",
            "6:    and     #0x1,r0",
            "8:    or      #0x1,r0",
            "a:    xor     #0x1,r0",
            "c:    mov     #-0x1,r12",
            "e:    add     #-0x1,r1",
            "10:    tst     #0xff,r0",
            "12:    and     #0xff,r0",
            "14:    or      #0xff,r0",
            "16:    xor     #0xff,r0",
            "18:    mov     #0x7f,r12",
            "1a:    add     #0x7f,r1",
            "1c:    tst     #0x7f,r0",
            "1e:    and     #0x7f,r0",
            "20:    or      #0x7f,r0",
            "22:    xor     #0x7f,r0",
            "24:    mov     #-0x80,r12",
            "26:    add     #-0x80,r1",
            "28:    tst     #0x80,r0",
            "2a:    and     #0x80,r0",
            "2c:    or      #0x80,r0",
            "2e:    xor     #0x80,r0",
        ]

        i = 0
        for text in loaded["rows"]:
            assert text["base"]["text"][0]["text"] == expected[i]
            i += 1

    def test_more_sh2_immediates(self) -> None:
        # test that the re_int regex is able to catch all these "boundary" numbers
        # since we have to match 0-9 one digit at a time
        #    0:   71 00           add     #0,r1
        #    2:   71 01           add     #1,r1
        #    4:   71 09           add     #9,r1
        #    6:   71 0a           add     #10,r1
        #    8:   71 0b           add     #11,r1
        #    a:   71 13           add     #19,r1
        #    c:   71 64           add     #100,r1
        #    e:   71 65           add     #101,r1
        #   10:   71 6d           add     #109,r1
        #   12:   71 6f           add     #111,r1
        #   14:   71 77           add     #119,r1
        #   16:   71 f7           add     #-9,r1
        #   18:   71 f6           add     #-10,r1
        #   1a:   71 f5           add     #-11,r1
        #   1c:   71 ed           add     #-19,r1
        #   1e:   71 9c           add     #-100,r1
        #   20:   71 9b           add     #-101,r1
        #   22:   71 93           add     #-109,r1
        #   24:   71 91           add     #-111,r1
        #   26:   71 89           add     #-119,r1
        sh2_theirs = "func_0606B760():\n   0:\t71 00       \tadd\t#0,r1\n   2:\t71 01       \tadd\t#1,r1\n   4:\t71 09       \tadd\t#9,r1\n   6:\t71 0a       \tadd\t#10,r1\n   8:\t71 0b       \tadd\t#11,r1\n   a:\t71 13       \tadd\t#19,r1\n   c:\t71 64       \tadd\t#100,r1\n   e:\t71 65       \tadd\t#101,r1\n  10:\t71 6d       \tadd\t#109,r1\n  12:\t71 6f       \tadd\t#111,r1\n  14:\t71 77       \tadd\t#119,r1\n  16:\t71 f7       \tadd\t#-9,r1\n  18:\t71 f6       \tadd\t#-10,r1\n  1a:\t71 f5       \tadd\t#-11,r1\n  1c:\t71 ed       \tadd\t#-19,r1\n  1e:\t71 9c       \tadd\t#-100,r1\n  20:\t71 9b       \tadd\t#-101,r1\n  22:\t71 93       \tadd\t#-109,r1\n  24:\t71 91       \tadd\t#-111,r1\n  26:\t71 89       \tadd\t#-119,r1"

        # just diff with self
        sh2_ours = sh2_theirs

        config = self.get_config()
        display = diff.Display(sh2_theirs, sh2_ours, config)
        loaded = json.loads(display.run_diff()[0])

        expected = [
            "0:    add     #0x0,r1",
            "2:    add     #0x1,r1",
            "4:    add     #0x9,r1",
            "6:    add     #0xa,r1",
            "8:    add     #0xb,r1",
            "a:    add     #0x13,r1",
            "c:    add     #0x64,r1",
            "e:    add     #0x65,r1",
            "10:    add     #0x6d,r1",
            "12:    add     #0x6f,r1",
            "14:    add     #0x77,r1",
            "16:    add     #-0x9,r1",
            "18:    add     #-0xa,r1",
            "1a:    add     #-0xb,r1",
            "1c:    add     #-0x13,r1",
            "1e:    add     #-0x64,r1",
            "20:    add     #-0x65,r1",
            "22:    add     #-0x6d,r1",
            "24:    add     #-0x6f,r1",
            "26:    add     #-0x77,r1",
        ]

        i = 0
        for text in loaded["rows"]:
            assert text["base"]["text"][0]["text"] == expected[i]
            i += 1

    def test_sh2_switch(self) -> None:
        # test that small switch tables get interpreted
        # 00000000 <_jtbl_test>:
        #    0:    2f e6           mov.l    r14,@-r15
        #    2:    e1 05           mov    #5,r1
        #    4:    34 16           cmp/hi    r1,r4
        #    6:    8d 17           bt.s    38 <_jtbl_test+0x38>
        #    8:    6e f3           mov    r15,r14
        #    a:    61 43           mov    r4,r1
        #    c:    31 1c           add    r1,r1
        #    e:    c7 02           mova    18 <_jtbl_test+0x18>,r0
        #   10:    01 1d           mov.w    @(r0,r1),r1
        #   12:    30 1c           add    r1,r0
        #   14:    40 2b           jmp    @r0
        #   16:    00 09           nop
        #   18:    00 10           .word 0x0010
        #   1a:    00 1c           mov.b    @(r0,r1),r0
        #   1c:    00 1c           mov.b    @(r0,r1),r0
        #   1e:    00 0c           mov.b    @(r0,r0),r0
        #   20:    00 14           mov.b    r1,@(r0,r0)
        #   22:    00 18           sett
        #   24:    a0 09           bra    3a <_jtbl_test+0x3a>
        #   26:    e0 01           mov    #1,r0
        #   28:    a0 07           bra    3a <_jtbl_test+0x3a>
        #   2a:    e0 02           mov    #2,r0
        #   2c:    a0 05           bra    3a <_jtbl_test+0x3a>
        #   2e:    e0 05           mov    #5,r0
        #   30:    a0 03           bra    3a <_jtbl_test+0x3a>
        #   32:    e0 06           mov    #6,r0
        #   34:    a0 01           bra    3a <_jtbl_test+0x3a>
        #   36:    e0 00           mov    #0,r0
        #   38:    e0 ff           mov    #-1,r0
        #   3a:    6f e3           mov    r14,r15
        #   3c:    00 0b           rts
        #   3e:    6e f6           mov.l    @r15+,r14
        objdump_raw = "00000000 <_jtbl_test>:\n   0:\t2f e6       \tmov.l\tr14,@-r15\n   2:\te1 05       \tmov\t#5,r1\n   4:\t34 16       \tcmp/hi\tr1,r4\n   6:\t8d 17       \tbt.s\t38 <_jtbl_test+0x38>\n   8:\t6e f3       \tmov\tr15,r14\n   a:\t61 43       \tmov\tr4,r1\n   c:\t31 1c       \tadd\tr1,r1\n   e:\tc7 02       \tmova\t18 <_jtbl_test+0x18>,r0\n  10:\t01 1d       \tmov.w\t@(r0,r1),r1\n  12:\t30 1c       \tadd\tr1,r0\n  14:\t40 2b       \tjmp\t@r0\n  16:\t00 09       \tnop\t\n  18:\t00 10       \t.word 0x0010\n  1a:\t00 1c       \tmov.b\t@(r0,r1),r0\n  1c:\t00 1c       \tmov.b\t@(r0,r1),r0\n  1e:\t00 0c       \tmov.b\t@(r0,r0),r0\n  20:\t00 14       \tmov.b\tr1,@(r0,r0)\n  22:\t00 18       \tsett\t\n  24:\ta0 09       \tbra\t3a <_jtbl_test+0x3a>\n  26:\te0 01       \tmov\t#1,r0\n  28:\ta0 07       \tbra\t3a <_jtbl_test+0x3a>\n  2a:\te0 02       \tmov\t#2,r0\n  2c:\ta0 05       \tbra\t3a <_jtbl_test+0x3a>\n  2e:\te0 05       \tmov\t#5,r0\n  30:\ta0 03       \tbra\t3a <_jtbl_test+0x3a>\n  32:\te0 06       \tmov\t#6,r0\n  34:\ta0 01       \tbra\t3a <_jtbl_test+0x3a>\n  36:\te0 00       \tmov\t#0,r0\n  38:\te0 ff       \tmov\t#-1,r0\n  3a:\t6f e3       \tmov\tr14,r15\n  3c:\t00 0b       \trts\t\n  3e:\t6e f6       \tmov.l\t@r15+,r14"

        config = self.get_config()
        processor = config.arch.proc(config)
        sh2_theirs = processor.preprocess_objdump(objdump_raw)

        # just diff with self
        sh2_ours = sh2_theirs

        config.arch.proc(config)
        display = diff.Display(sh2_theirs, sh2_ours, config)
        loaded = json.loads(display.run_diff()[0])

        expected = [
            "18:    .word   0x0010 ! (28) ",
            "1a:    .word   0x001c ! (34) ",
            "1c:    .word   0x001c ! (34) ",
            "1e:    .word   0x000c ! (24) ",
            "20:    .word   0x0014 ! (2c) ",
            "22:    .word   0x0018 ! (30) ",
        ]

        # check if literal pool is correctly guessed
        i = 0
        for text in loaded["rows"][12:18]:
            row = text["base"]["text"][0]["text"]
            row += text["base"]["text"][1]["text"]
            row += text["base"]["text"][2]["text"]

            assert row == expected[i]
            i += 1

    def test_branch(self) -> None:
        # test that bt.s and bra get ~>
        # func():
        #    0:   8d 02           bt.s    8 <lab_0606B780>
        #    2:   6e f3           mov     r15,r14
        #    4:   a0 01           bra     a <lab_0606B8E0>
        #    6:   00 09           nop

        # 00000008 <lab_0606B780>:
        # lab_0606B780():
        #    8:   db 32           mov.l   d4 <lab_0606B8E0+0xca>,r11

        # 0000000a <lab_0606B8E0>:
        # lab_0606B8E0():
        #    a:   00 0b           rts
        #    c:   00 09           nop
        sh2_theirs = "func():\n   0:\t8d 02       \tbt.s\t8 <lab_0606B780>\n   2:\t6e f3       \tmov\tr15,r14\n   4:\ta0 01       \tbra\ta <lab_0606B8E0>\n   6:\t00 09       \tnop\t\n\n00000008 <lab_0606B780>:\nlab_0606B780():\n   8:\tdb 32       \tmov.l\td4 <lab_0606B8E0+0xca>,r11\n\n0000000a <lab_0606B8E0>:\nlab_0606B8E0():\n   a:\t00 0b       \trts\t\n   c:\t00 09       \tnop\t"
        sh2_ours = sh2_theirs

        config = self.get_config()
        display = diff.Display(sh2_theirs, sh2_ours, config)
        loaded = json.loads(display.run_diff()[0])

        # bt.s    8
        print(loaded["rows"][0]["base"]["text"][1]["text"] == "~>")
        print(loaded["rows"][0]["base"]["text"][1]["key"] == "8")

        # bra     a
        print(loaded["rows"][2]["base"]["text"][1]["text"] == "~>")
        print(loaded["rows"][2]["base"]["text"][1]["key"] == "10")


if __name__ == "__main__":
    unittest.main()
