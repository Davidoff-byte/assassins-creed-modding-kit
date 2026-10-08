import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import java.io.PrintWriter;

public class Action90SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action90.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        // class descriptors: +0x30 = the ctor. Find the descriptors for the node-family ctors.
        long[] ctors = { 0x0052A4A0L, 0x00503330L, 0x006DEFA0L, 0x00504880L };
        String[] names = { "base-node-ctor", "mid-ctor", "derived-ctor", "node-desc-ctor" };
        out.println("=== descriptors whose +0x30 = a node-family ctor ===");
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            if (!b.isInitialized() || b.isWrite()) { continue; }
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

        // FUN_005efc90 - the post-create init
        Function fn = getFunctionAt(toAddr(0x005EFC90L));
        out.println("=== FUN_005efc90 (post-create) ===");
        if (fn != null) {
            DecompileResults dr = ifc.decompileFunction(fn, 120, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 7000) { c = c.substring(0, 7000) + "\n...(truncated)"; }
                out.println(c);
            }
        }
        out.close();
    }
}
