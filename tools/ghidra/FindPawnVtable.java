// FindPawnVtable.java - fingerprint the ADishonoredPlayerPawn vtable.
// The Pawn's exec thunks dispatch to these vtable slots:
//   +0x788 OnAddPower  +0x78c OnRemovePower  +0x798 OnMaxPowers
//   +0x79c OnMinPowers +0x7b8 OnTogglePowerWheel +0x7e4 OnCancelPlayerActivePower
// Find the code-pointer table that has valid code at every one of those
// offsets, then decompile them.
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import java.io.PrintWriter;
import java.util.LinkedHashMap;

public class FindPawnVtable extends GhidraScript {

    private static final long[] SLOTS = { 0x788L, 0x78cL, 0x798L, 0x79cL, 0x7b8L, 0x7e4L };

    private long u32(Address a) {
        try {
            return currentProgram.getMemory().getInt(a) & 0xffffffffL;
        } catch (Exception e) {
            return -1;
        }
    }

    private boolean isCode(long v) {
        if (v < 0x00400000L || v >= 0x01000000L) {
            return false;
        }
        MemoryBlock b = currentProgram.getMemory().getBlock(toAddr(v));
        return b != null && b.isExecute();
    }

    @Override
    public void run() throws Exception {
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter(
            "C:\\Users\\Administrator\\ghidra_scripts\\pawn_vtable_out.txt", "UTF-8");

        LinkedHashMap<Address, String> targets = new LinkedHashMap<>();

        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            if (!b.isInitialized() || b.isExecute()) {
                continue;
            }
            Address start = b.getStart();
            long size = b.getSize();
            long i = 0;
            while (i + 4 <= size) {
                if (!isCode(u32(start.add(i)))) {
                    i += 4;
                    continue;
                }
                long runLen = 0;
                long j = i;
                while (j + 4 <= size && isCode(u32(start.add(j)))) {
                    runLen++;
                    j += 4;
                }
                long bytes = runLen * 4;
                if (bytes >= 0x7e8L) {
                    Address vt = start.add(i);
                    boolean all = true;
                    for (long off : SLOTS) {
                        if (!isCode(u32(vt.add(off)))) {
                            all = false;
                            break;
                        }
                    }
                    if (all) {
                        out.println("PAWN VTABLE CANDIDATE " + vt
                            + " entries=" + runLen);
                        for (long off : SLOTS) {
                            long v = u32(vt.add(off));
                            Function f = getFunctionAt(toAddr(v));
                            out.println(String.format("    +0x%X -> %08X  %s",
                                off, v, f != null ? f.getName() : "(no func)"));
                            targets.put(toAddr(v), String.format(
                                "+0x%X of %s", off, vt));
                        }
                    }
                }
                i = j > i ? j : i + 4;
            }
        }

        out.println();
        out.println("=== decompiling " + targets.size() + " slot functions ===");
        for (var e : targets.entrySet()) {
            out.println("==================================================");
            out.println("FUNCTION " + e.getKey() + "  " + e.getValue());
            Function f = getFunctionAt(e.getKey());
            if (f == null) {
                out.println("  (no function)");
                continue;
            }
            DecompileResults res = ifc.decompileFunction(f, 120, monitor);
            if (res != null && res.decompileCompleted() && res.getDecompiledFunction() != null) {
                out.println(res.getDecompiledFunction().getC());
            } else {
                out.println("  decompile failed");
            }
        }
        out.close();
        ifc.dispose();
        println("FindPawnVtable done: " + targets.size() + " targets");
    }
}
