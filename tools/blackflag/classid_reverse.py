import re
import zlib

# class ids from the engine's own mass-creator census
IDS = {
    0x9467F2BB: "dominant x246 (crowd?)",
    0x9336FC8B: "x50",
    0x4368101B: "x47",
    0x536E963B: "x37",
    0xEC658D29: "x21",
    0xA2B7E917: "x20",
    0x13237FE9: "x20",
    0x0984415E: "Entity (known)",
    0x01437462: "x12",
    0x26644504: "x10",
}
TSET = set(IDS.keys())

corpus = r"C:\Users\Administrator\Documents\Default Project\bf-coop\tools\forge_names.txt"
hits = {}
tested = 0

with open(corpus, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        s = line.rstrip("\n")
        if not s or len(s) < 3 or len(s) > 60:
            continue
        tested += 1
        for v in (s, s.lower(), s.upper()):
            h = zlib.crc32(v.encode("latin-1", errors="replace")) & 0xFFFFFFFF
            if h in TSET and h not in hits:
                hits[h] = s

print(f"tested {tested} corpus names")
for i, label in IDS.items():
    print(f"  {hex(i)} ({label}): {hits.get(i, '(no match)')}")

# also add common word guesses beyond the corpus
words = ["Entity", "EntityGroup", "StaticEntity", "Static", "DynamicEntity", "Dynamic",
         "Person", "Human", "Character", "Actor", "Pedestrian", "Civilian", "Crowd",
         "Prop", "Object", "Scene", "SceneEntity", "WorldEntity", "GameEntity",
         "Building", "Structure", "Terrain", "Water", "Vegetation", "Tree", "Rock",
         "Vehicle", "Ship", "Boat", "Animal", "Creature", "Item", "Weapon",
         "Light", "Sound", "Emitter", "Particle", "Effect", "SoundEmitter",
         "VisionZone", "Zone", "Volume", "Trigger", "Marker"]
print()
print("wordlist pass:")
for w in words:
    h = zlib.crc32(w.encode()) & 0xFFFFFFFF
    if h in TSET:
        print(f"  {hex(h)} = '{w}'")
