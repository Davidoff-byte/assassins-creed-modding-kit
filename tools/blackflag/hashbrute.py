import zlib
import itertools

TARGETS = {
    0x49BB47AC: "crowd-template (captured spawn)",
    0x559DD66B: "catalog key",
    0x87F1FE1A: "catalog key",
    0x465A79BF: "catalog key",
    0xC0A8689E: "catalog key",
    0x7165D1E7: "catalog key",
    0xFE99A1E8: "catalog key",
}

# candidate name parts in the style the engine uses (Entity, EntityGroup, ManagedObject...)
words = [
    "Entity", "EntityGroup", "Avatar", "Character", "Actor", "Human", "Humanoid",
    "Pedestrian", "Civilian", "Citizen", "Villager", "Worker", "Npc", "NPC", "Person",
    "Male", "Female", "Man", "Woman", "Child", "Adult", "Old", "Young",
    "Guard", "Soldier", "Pirate", "Sailor", "Captain", "Officer", "Marine", "Navy",
    "Assassin", "Templar", "Hunter", "Bandit", "Thug", "Beggar", "Merchant", "Trader",
    "Crowd", "Population", "Ambient", "Wanderer", "Walker", "Idle",
    "Dock", "Dockworker", "Farmer", "Fisher", "Fisherman", "Smuggler", "Slave",
    "Spanish", "English", "British", "French", "Dutch", "Native", "Tavern",
    "Dancer", "Musician", "Noble", "Rich", "Poor", "Pauper", "Whore", "Prostitute",
    "Crew", "Deckhand", "Bosun", "Gunner", "Lookout", "Scout", "Sharpshooter",
]
prefixes = ["", "AC4_", "ACBF_", "AC4BF_", "chr_", "CHR_", "npc_", "Npc_", "NPC_", "ped_", "PED_", "civ_", "CIV_"]
suffixes = ["", "_01", "01", "1", "_A", "_Male", "Male", "_Female", "Female", "_Human",
            "_V01", "_V1", "_A01", "Base", "_Base", "Entity", "_Entity"]

TARGET_SET = set(TARGETS.keys())
tested = 0
hits = []

def test(name):
    global tested
    tested += 1
    for v in (name, name.lower(), name.upper()):
        h = zlib.crc32(v.encode()) & 0xFFFFFFFF
        if h in TARGET_SET:
            hits.append((TARGETS[h], v, hex(h)))
            return

for w in words:
    for p in prefixes:
        for s in suffixes:
            test(p + w + s)

# also the raw words + two-word combos with the style separators
for a, b in itertools.product(["Npc", "NPC", "Pedestrian", "Civilian", "Crowd", "Ambient", "Human"], ["Male", "Female", "Man", "Woman", "Adult", "A", "B"]):
    for sep in ["", "_", "-"]:
        test(a + sep + b)
        test(b + sep + a)

print(f"tested: {tested}")
print("=== MATCHES ===")
for t, s, h in hits:
    print(f"  {h}  '{s}'  <= {t}")
if not hits:
    print("  (none)")
