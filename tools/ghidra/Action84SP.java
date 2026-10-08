import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action84SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action84.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        // controller vtable 0x26fa898
        out.println("=== vtable 0x026fa898 (controller class) slots 0..15 ===");
        for (int i = 0; i < 16; i++) {
            long off = 0x026FA898L + i * 4;
            int v = getInt(toAddr(off));
            Function cf = getFunctionContaining(toAddr(v & 0xFFFFFFFFL));
            out.println(String.format("  [%02d]+0x%02X: 0x%08X %s", i, i * 4, v, cf != null ? cf.getName() : ""));
        }
        out.println();

        // who writes the vtable (the ctor) + refs
        out.println("=== refs to 0x026fa898 ===");
        for (Reference r : getReferencesTo(toAddr(0x026FA898L))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  from " + r.getFromAddress() + (cf != null ? " in " + cf.getName() : ""));
        }
        out.println();

        // dump the vtable-adjacent data (class metadata often sits right after)
        out.println("=== data around 0x026fa898 (as dwords, 32) ===");
        for (int i = 0; i < 32; i++) {
            long off = 0x026FA898L + i * 4;
            int v = getInt(toAddr(off));
            Function cf = getFunctionContaining(toAddr(v & 0xFFFFFFFFL));
            out.println(String.format("  0x%08X: 0x%08X %s", off, v, cf != null ? cf.getName() : ""));
        }
        out.close();
    }
}
