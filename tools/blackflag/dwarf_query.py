#!/usr/bin/env python3
"""Targeted DWARF query: dump full definitions (members, enum values, params) for
types whose names match the given patterns. One pass over the PS3 gold ELF."""
import sys, time
from elftools.elf.elffile import ELFFile

ELF = r'D:\Games\acbf_ps3_gold\scimitar_final.elf'
PATTERNS = ['NavigationTarget', 'NavigationCommands', 'NavigationSpeed', 'NavigationContextID',
            'CSrvNavigation', 'NavigationAbilities', 'MetaLinkValidationData']
if len(sys.argv) > 1 and sys.argv[1] == '--patterns':
    PATTERNS = sys.argv[2:]

def name(die):
    a = die.attributes.get('DW_AT_name')
    if a is None:
        return None
    v = a.value
    return v.decode('latin1', 'replace') if isinstance(v, bytes) else str(v)

def fmt_attrs(die):
    parts = []
    for k, v in die.attributes.items():
        ks = k.replace('DW_AT_', '')
        if ks in ('name', 'decl_file', 'decl_line', 'decl_column', 'type', 'external',
                  'declaration', 'artificial', 'prototyped'):
            if ks == 'type':
                parts.append('type=@%s' % v.value)
            continue
        parts.append('%s=%s' % (ks, v.value))
    return ' '.join(parts)

seen = set()
def dump_tree(die, depth):
    key = (die.tag, name(die), getattr(die, 'offset', None), depth)
    line = '  ' * depth + die.tag.replace('DW_TAG_', '') + ' "' + str(name(die)) + '"'
    a = fmt_attrs(die)
    if a:
        line += '  ' + a
    print(line)
    for ch in die.iter_children():
        dump_tree(ch, depth + 1)

def main():
    t0 = time.time()
    f = open(ELF, 'rb')
    elf = ELFFile(f)
    di = elf.get_dwarf_info()
    n_printed = 0
    for cu in di.iter_CUs():
        for die in cu.iter_DIEs():
            nm = name(die)
            if not nm:
                continue
            if not any(p in nm for p in PATTERNS):
                continue
            if die.tag not in ('DW_TAG_class_type', 'DW_TAG_structure_type',
                               'DW_TAG_enumeration_type', 'DW_TAG_union_type',
                               'DW_TAG_typedef', 'DW_TAG_subprogram'):
                continue
            # dedupe: print each (tag, name) once per distinct attribute set is too much;
            # print classes/enums always, subprograms only if they have children (definitions)
            key = (die.tag, nm)
            if die.tag == 'DW_TAG_subprogram':
                # constructors and small setters are interesting; other methods too many
                low = nm.rsplit('::', 1)[-1]
                if not (low in ('NavigationTarget', 'NavigateTo', 'NavigateToNavTarget',
                                'NavigateCancel', 'IsTargetReached', 'SetMovementType',
                                '~NavigationTarget') or low.startswith('NavigationTarget')):
                    continue
            print('=' * 100)
            dump_tree(die, 0)
            n_printed += 1
        print('-- progress: cu done, printed=%d %.0fs --' % (n_printed, time.time() - t0),
              file=sys.stderr, flush=True)
    print('DONE printed=%d %.0fs' % (n_printed, time.time() - t0), file=sys.stderr)

main()
