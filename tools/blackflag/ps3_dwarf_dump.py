#!/usr/bin/env python3
"""One-pass filtered DWARF extraction from the PS3 ELF:
- CU names (source files)
- class/struct layouts (bases + members w/ offsets) grouped by keyword families
- subprogram signatures (name, low_pc, param types) grouped by keyword families
- a compact index of ALL named types with sizes
"""
import os
import struct
import sys
import time

from elftools.elf.elffile import ELFFile

ELF = sys.argv[1] if len(sys.argv) > 1 else r'D:\Games\acbf_ps3_gold\scimitar_final.elf'
OUT = sys.argv[2] if len(sys.argv) > 2 else r'C:\Users\Administrator\Documents\Default Project\bf-coop\logs\dwarf'
os.makedirs(OUT, exist_ok=True)

GROUPS = {
    'health_combat': ['health', 'damage', 'combat', 'melee', 'kill', 'death', 'ragdoll',
                      'wound', 'hurt', 'weapon', 'attack', 'defen', 'stagger', 'knife',
                      'sword', 'gun', 'ammo', 'fight', 'stun', 'counter'],
    'ai_entity': ['entityai', 'behav', 'bhv', 'statechart', 'perception', 'sensor', 'navmesh',
                  'aicommand', 'aiaction', 'service', 'npc', 'crowd'],
    'entity_core': ['scimitar::entity', 'scimitar::object', 'handle', 'reference', 'component',
                    'sceneactor', 'scene', 'world'],
    'anim': ['anim', 'skeleton', 'pose', 'kinematic', 'locomotion', 'climb', 'parkour', 'fsm'],
    'player_ship': ['player', 'ship', 'naval', 'crew', 'camera'],
    'stream_save': ['stream', 'save', 'spawn', 'load', 'cache', 'lod'],
    'network_mp': ['network', 'sync', 'replicat', 'session', 'lobby'],
}

def fname(die, cu_namemap):
    a = die.attributes.get('DW_AT_name')
    if a is None:
        return None
    v = a.value
    return v.decode('latin1', 'replace') if isinstance(v, bytes) else str(v)

def typename(die, cu_namemap):
    a = die.attributes.get('DW_AT_type')
    if a is None:
        return None
    off = a.value
    return cu_namemap.get(off)

def member_off(child):
    off = child.attributes.get('DW_AT_data_member_location')
    if off is None:
        return -1
    v = off.value
    if isinstance(v, int):
        return v
    try:
        # location expression: usually [DW_OP_plus_uconst(0x23), n]
        if len(v) >= 2 and int(v[0]) == 0x23:
            return int(v[1])
        if len(v) == 1 and int(v[0]) < 0x10000:
            return int(v[0])
    except Exception:
        pass
    return -1

def main():
    t0 = time.time()
    f = open(ELF, 'rb')
    elf = ELFFile(f)
    di = elf.get_dwarf_info()
    files = {g: open(os.path.join(OUT, g + '_types.txt'), 'w', encoding='latin1') for g in GROUPS}
    ffiles = {g: open(os.path.join(OUT, g + '_funcs.txt'), 'w', encoding='latin1') for g in GROUPS}
    idx = open(os.path.join(OUT, 'all_types_index.txt'), 'w', encoding='latin1')
    cus = open(os.path.join(OUT, 'cus.txt'), 'w', encoding='latin1')

    n_types = n_funcs = n_cu = 0
    for cu in di.iter_CUs():
        n_cu += 1
        name = cu.get_top_DIE().attributes.get('DW_AT_name')
        cuname = name.value.decode('latin1', 'replace') if name is not None else '?'
        cus.write(cuname + '\n')
        dies = list(cu.iter_DIEs())
        namemap = {}
        for die in dies:
            nm = fname(die, None)
            if nm:
                namemap[die.offset] = nm

        low = cuname.lower()
        for die in dies:
            tag = die.tag
            if tag in ('DW_TAG_class_type', 'DW_TAG_structure_type', 'DW_TAG_union_type'):
                nm = namemap.get(die.offset)
                if not nm:
                    continue
                size = die.attributes.get('DW_AT_byte_size')
                size = size.value if size is not None else -1
                idx.write('%s\t%d\n' % (nm, size))
                n_types += 1
                key = (nm + ' ' + low).lower()
                hits = [g for g, kws in GROUPS.items() if any(k in key for k in kws)]
                if not hits:
                    continue
                lines = ['class %s  size=%s' % (nm, size)]
                for child in die.iter_children():
                    if child.tag == 'DW_TAG_inheritance':
                        b = typename(child, namemap)
                        lines.append('  : %s @ %s' % (b, member_off(child)))
                    elif child.tag == 'DW_TAG_member':
                        mn = fname(child, namemap)
                        mt = typename(child, namemap)
                        boff = member_off(child)
                        bit = child.attributes.get('DW_AT_bit_size')
                        extra = ''
                        if bit is not None:
                            bpos = child.attributes.get('DW_AT_bit_offset')
                            extra = ' bit<%s@%s>' % (bit.value, bpos.value if bpos is not None else '?')
                        lines.append('  +0x%-4s %-40s %s%s' % (('%X' % boff) if boff >= 0 else '?', mn, mt, extra))
                out = '\n'.join(lines) + '\n\n'
                for g in hits:
                    files[g].write(out)
            elif tag == 'DW_TAG_subprogram':
                nm = namemap.get(die.offset)
                if not nm:
                    continue
                lowpc = die.attributes.get('DW_AT_low_pc')
                lowpc = lowpc.value if lowpc is not None else 0
                key = (nm + ' ' + low).lower()
                hits = [g for g, kws in GROUPS.items() if any(k in key for k in kws)]
                if not hits:
                    continue
                n_funcs += 1
                params = []
                for child in die.iter_children():
                    if child.tag == 'DW_TAG_formal_parameter':
                        params.append(typename(child, namemap) or '?')
                line = '0x%08X %s(%s)\n' % (lowpc, nm, ', '.join(params))
                for g in hits:
                    ffiles[g].write(line)
        if n_cu % 100 == 0:
            print('cu=%d types=%d funcs=%d  %.0fs' % (n_cu, n_types, n_funcs, time.time() - t0), flush=True)

    cus.close(); idx.close()
    for x in list(files.values()) + list(ffiles.values()):
        x.close()
    print('DONE cu=%d types=%d funcs=%d  %.0fs' % (n_cu, n_types, n_funcs, time.time() - t0))

main()
