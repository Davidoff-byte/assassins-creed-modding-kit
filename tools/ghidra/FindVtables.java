// FindVtables.java - locate large vtables in non-executable initialized
// segments (runs of function pointers), then decompile the slot that
// ADishonoredPlayerPawnexecOnCancelPlayerActivePower dispatches to (+0x7e4),
// plus the cheat-manager Blink slots (+0x510/+0x514).
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import java.io.PrintWriter;
import java.util.LinkedHashMap;

public class FindVtables extends GhidraScript {

    private long u32(Address a) {
        try {
            return currentProgram.getMemory().getInt(a) & 0xffffffffL;
        } catch (Exception e) {
            return -1;
        }
    }

    private boolean isFunc(long v) {
        if (v < 0x00400000L || v >= 0x01000000L) {
            return false;
        }
        return getFunctionAt(toAddr(v)) != null;
    }

    private static final long MIN_BYTES = 0x7f0L;

    @Override
    public void run() throws Exception {
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter(
            "C:\\Users\\Administrator\\ghidra_scripts\\vtables_out.txt", "UTF-8");

        LinkedHashMap<Address, String> slots = new LinkedHashMap<>();

        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            if (!b.isInitialized() || b.isExecute()) {
                continue;
            }
            Address start = b.getStart();
            long size = b.getSize();
            long i = 0;
            while (i + 4 <= size) {
                Address a = start.add(i);
                if (!isFunc(u32(a))) {
                    i += 4;
                    continue;
                }
                long runLen = 0;
                long j = i;
                while (j + 4 <= size && isFunc(u32(start.add(j)))) {
                    runLen++;
                    j += 4;
                }
                long bytes = runLen * 4;
                if (bytes >= MIN_BYTES) {
                    Address vt = start.add(i);
                    out.println(String.format(
                        "VTABLE %s  entries=%d  bytes=0x%X", vt, runLen, bytes));
                    // slot at +0x7e4 and +0x510/+0x514
                    for (long off : new long[] { 0x7e4L, 0x510L, 0x514L }) {
                        Address sa = vt.add(off);
                        long v = u32(sa);
                        if (isFunc(v)) {
                            Function f = getFunctionAt(toAddr(v));
                            out.println(String.format(
                                "    slot +0x%X -> %08X  %s", off, v, f.getName()));
                            slots.put(toAddr(v), f.getName() + " (+0x"
                                + Long.toHexString(off) + " from " + vt + ")");
                        }
                    }
                }
                i = j > i ? j : i + 4;
            }
        }

        out.println();
        out.println("=== decompiling " + slots.size() + " slot functions ===");
        for (var e : slots.entrySet()) {
            out.println("==================================================");
            out.println("FUNCTION " + e.getKey() + "  " + e.getValue());
            DecompileResults res = ifc.decompileFunction(e.getKey() != null
                ? getFunctionAt(e.getKey()) : null, 120, monitor);
            if (res != null && res.decompileCompleted() && res.getDecompiledFunction() != null) {
                out.println(res.getDecompiledFunction().getC());
            } else {
                out.println("  decompile failed");
            }
        }
        out.close();
        ifc.dispose();
        println("FindVtables done: " + slots.size() + " slots");
    }
}
