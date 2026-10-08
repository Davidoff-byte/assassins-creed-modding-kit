import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import java.io.PrintWriter;

public class Action66SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action66.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        // 1) the thread wrapper FUN_00a1ea30
        Function wrap = getFunctionAt(toAddr(0x00A1EA30L));
        out.println("=== FUN_00a1ea30 (thread wrapper) ===");
        if (wrap != null) {
            DecompileResults dr = ifc.decompileFunction(wrap, 60, monitor);
            if (dr.getDecompiledFunction() != null) {
                out.println(dr.getDecompiledFunction().getC());
            }
        }

        // 2) vtable at 0x01e3e2f8 (StartupSequenceThread obj vtable)
        out.println("=== vtable 0x01e3e2f8 entries ===");
        for (int i = 0; i < 24; i++) {
            long slot = 0x01E3E2F8L + i * 4;
            int v = getInt(toAddr(slot));
            if (v == 0) { out.println(String.format("  [%02d] 0", i)); continue; }
            Function cf = getFunctionContaining(toAddr(v & 0xFFFFFFFFL));
            out.println(String.format("  [%02d] 0x%08X %s", i, v, cf != null ? cf.getName() : ""));
        }
        // also the other vtable mentioned: 01e3e260
        out.println("=== vtable 0x01e3e260 entries ===");
        for (int i = 0; i < 12; i++) {
            long slot = 0x01E3E260L + i * 4;
            int v = getInt(toAddr(slot));
            if (v == 0) { out.println(String.format("  [%02d] 0", i)); continue; }
            Function cf = getFunctionContaining(toAddr(v & 0xFFFFFFFFL));
            out.println(String.format("  [%02d] 0x%08X %s", i, v, cf != null ? cf.getName() : ""));
        }
        out.close();
    }
}
