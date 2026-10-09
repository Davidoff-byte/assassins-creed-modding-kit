#!/usr/bin/env python3
import sys
sys.path.insert(0, r'C:\Users\Administrator\Documents\Default Project\bf-coop\tools')
import forge_toc as ft

info = ft.parse_forge(r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\DataPC_extra_chr.forge")
m = {}
for e in info['entries']:
    if e.get('hash32') and e.get('name'):
        m[e['hash32']] = e['name']

print('looking up 0x2821090F ->', m.get(0x2821090F))
print()
for n in ['CHR_U_Duncan_Walpole', 'CHR_U_EdwardKenwayStandard', 'CHR_C_F_Poor', 'CHR_C_F_Rich',
          'CHR_G_Spanish_Soldier', 'CHR_C_M_Slaves', 'CHR_C_M_Spanish_Medium',
          'CHR_C_M_Generic_Sailors', 'CHR_G_M_Pirate_Jackdaw_Sailors',
          'CHR_P_EdwardKenway_Default_Body', 'CHR_P_EdwardKenway_Default']:
    found = [hex(e['hash32']) for e in info['entries'] if e.get('name') == n]
    print('%-42s %s' % (n, found))
