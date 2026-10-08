import ghidra.app.decompiler.DecompInterface;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.mem.MemoryBlock;
import java.io.PrintWriter;

public class Action91SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action91.txt", "UTF-8");

        // class descriptors: +0x30 = the ctor. Scan ALL initialized blocks (descriptors live
        // in the writable .data).
        long[] ctors = { 0x0052A4A0L, 0x00503330L, 0x006DEFA0L, 0x00504880L, 0x006DEFC0L };
        String[] names = { "base-node-ctor", "mid-ctor", "derived-ctor", "?5 04880", "?6 DEFC0" };
        out.println("=== descriptors (any block) whose +0x30 = a node-family ctor ===");
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            if (!b.isInitialized()) { continue; }
            long start = b.getStart().getOffset();
            long end   = b.getEnd().getOffset();
            for (long p = start; p + 0x60 <= end; p += 4) {
                int ctor = getInt(toAddr(p + 0x30));
                long cv = ctor & 0xFFFFFFFFL;
                for (int i = 0; i < ctors.length; i++) {
                    if (cv == ctors[i]) {
                        int id  = getInt(toAddr(p + 0x10));
                        int h14 = getInt(toAddr(p + 0x14));
                        int vc  = getInt(toAddr(p + 0x0C));
                        out.println(String.format("  desc=0x%08X %s id=0x%08X h14=0x%08X +0C=0x%08X",
                            p, names[i], id, h14, vc));
                    }
                }
            }
        }
        out.println();

        // also: what descriptors exist near 0x275CD28 (the neighbours in the table)?
        out.println("=== 0x275ccc0 .. 0x275cf00 as descriptors (id at +0x10) ===");
        for (long p = 0x0275CCC0L; p < 0x0275CF00L; p += 4) {
            int id  = getInt(toAddr(p + 0x10));
            int ctor = getInt(toAddr(p + 0x30));
            if (id != 0 || ctor != 0) {
                out.println(String.format("  base=0x%08X id=0x%08X ctor=0x%08X", p, id, ctor));
            }
        }
        out.close();
    }
}
