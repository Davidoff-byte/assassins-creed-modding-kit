import ghidra.app.script.GhidraScript;
import ghidra.program.model.mem.MemoryBlock;
import java.io.PrintWriter;

public class Action101SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action101.txt", "UTF-8");
        long CLONE = 0x00663590L;
        out.println("=== vtables containing FUN_00663590 in the first 64 slots ===");
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            if (!b.isInitialized() || b.isWrite()) { continue; }
            long start = b.getStart().getOffset();
            long end   = b.getEnd().getOffset();
            for (long p = start; p + 4 <= end; p += 4) {
                int v = getInt(toAddr(p));
                if ((v & 0xFFFFFFFFL) == CLONE) {
                    // found a slot referencing the registrar; walk back to a likely vtable base
                    out.println(String.format("  slot at 0x%08X", p));
                }
            }
        }
        out.close();
    }
}
