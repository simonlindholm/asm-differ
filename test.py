import unittest
import diff
import json

class TestSh2(unittest.TestCase):
    def get_config(self):
        arch = diff.get_arch('sh2')
        formatter = diff.JsonFormatter(arch_str='sh2')
        config = diff.Config(
            arch=arch, 
            diff_obj=True, 
            objfile='', 
            make=False, 
            source_old_binutils=True, 
            diff_section='.text', 
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
            stop_at_ret=False, 
            ignore_large_imms=False, 
            ignore_addr_diffs=True, 
            algorithm='levenshtein', 
            reg_categories={})
        return config

    # check that comment <> regex has ? to avoid "<func_060E8780+0x44>,r1      ! 60e87d0"
    # all being a comment for:
    # mov.l   44 <func_060E8780+0x44>,r1      ! 60e87d0
    def test_sh2_comment(self):
        # parser specifically looks for tabs so make sure they are represented

        # 16:   d1 0b           mov.l   44 <func_060E8780+0x44>,r1      ! 60e87d0
        sh2_theirs = "  16:\td1 0b       \tmov.l\t44 <func_060E8780+0x44>,r1\t! 60e87d0\n"

        # 16:   d1 0b           mov.l   44 <_func_060E8780+0x44>,r1     ! 0 <_func_060E8780>
        sh2_ours = "  16:\td1 0b       \tmov.l\t44 <_func_060E8780+0x44>,r1\t! 0 <_func_060E8780>\n"

        config = self.get_config()
        display = diff.Display(sh2_theirs, sh2_ours, config)
        loaded = json.loads(display.run_diff()[0])

        curr = loaded['rows'][0]['current']['src_comment']

        assert(curr != "<_func_060E8780+0x44>,r1     ! 0 <_func_060E8780>")
        assert(curr == "<_func_060E8780+0x44>")

    def test_sh2_immediates(self):
        # test parsing these immediates
        # func_0606B760():
        # 0:   ec 01           mov     #1,r12
        # 2:   71 01           add     #1,r1
        # 4:   ec ff           mov     #-1,r12
        # 6:   71 ff           add     #-1,r1
        # 8:   ec 7f           mov     #127,r12
        # a:   71 7f           add     #127,r1
        # c:   ec 80           mov     #-128,r12
        # e:   71 80           add     #-128,r1
        sh2_theirs = 'func_0606B760():\n   0:\tec 01       \tmov\t#1,r12\n   2:\t71 01       \tadd\t#1,r1\n   4:\tec ff       \tmov\t#-1,r12\n   6:\t71 ff       \tadd\t#-1,r1\n   8:\tec 7f       \tmov\t#127,r12\n   a:\t71 7f       \tadd\t#127,r1\n   c:\tec 80       \tmov\t#-128,r12\n   e:\t71 80       \tadd\t#-128,r1'

        # just diff with self
        sh2_ours = sh2_theirs 

        config = self.get_config()
        display = diff.Display(sh2_theirs, sh2_ours, config)
        loaded = json.loads(display.run_diff()[0])

        expected = [
            "0:    mov     #1,r12",
            "2:    add     #1,r1",
            "4:    mov     #-1,r12",
            "6:    add     #-1,r1",
            "8:    mov     #127,r12",
            "a:    add     #127,r1",
            "c:    mov     #-128,r12",
            "e:    add     #-128,r1"
        ]

        i = 0
        for text in loaded['rows']:
            assert(text['base']['text'][0]['text'] == expected[i])
            i += 1

if __name__ == '__main__':
    unittest.main()