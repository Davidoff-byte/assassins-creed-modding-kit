import ghidra.app.decompiler.DecompInterface;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import java.io.PrintWriter;

public class Action76SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action76.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long CLONE = 0x006DEFF0L;
        out.println("=== vtables whose slot 3 (0xC) = the clone (0x006DEFF0) ===");
        int found = 0;
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            if (!b.isInitialized()) { continue; }
            long start = b.getStart().getOffset();
            long end   = b.getEnd().getOffset();
            if (end - start > 0x800000L) { continue; } // skip giant blocks (heap-ish)
            for (long p = start; p + 4 <= end; p += 4) {
                int vt = getInt(toAddr(p));
                long vv = vt & 0xFFFFFFFFL;
                if (vv < 0x400000L || vv >= 0x2F00000L) { continue; }
                if (vv == CLONE) { continue; }
                try {
                    int slot3 = getInt(toAddr(vv + 0xCL));
                    if ((slot3 & 0xFFFFFFFFL) == CLONE) {
                        int slot0 = getInt(toAddr(vv));
                        Function f0 = getFunctionContaining(toAddr(slot0 & 0xFFFFFFFFL));
                        int slot1 = getInt(toAddr(vv + 4));
                        int slot2 = getInt(toAddr(vv + 8));
                        out.println(String.format("  vt=0x%08X slot0=0x%08X(%s) slot1=0x%08X slot2=0x%08X",
                            vv, slot0, f0 != null ? f0.getName() : "?", slot1, slot2));
                        found++;
                        if (found > 60) { out.println("...(capped)"); break; }
                    }
                } catch (Exception e) {
                }
            }
            if (found > 60) { break; }
        }
        out.println("total: " + found);
        out.close();
    }
}
