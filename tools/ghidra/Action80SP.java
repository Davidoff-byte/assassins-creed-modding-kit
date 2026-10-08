import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action80SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action80.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        // 1) the player's class descriptor 0x275CD28 - dump its fields (hash, size, ctor)
        out.println("=== class descriptor 0x0275CD28 (player's class) ===");
        for (int i = 0; i < 24; i++) {
            long off = 0x0275CD28L + i * 4;
            int v = getInt(toAddr(off));
            Function cf = getFunctionContaining(toAddr(v & 0xFFFFFFFFL));
            out.println(String.format("  +0x%02X: 0x%08X %s", i * 4, v, cf != null ? cf.getName() : ""));
        }
        out.println();

        // 2) who references the descriptor (the spawn sites for the player class)
        out.println("=== refs to 0x0275cd28 ===");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(0x0275CD28L))) {
            out.println("  from " + r.getFromAddress());
            Function cf = getFunctionContaining(r.getFromAddress());
            if (cf != null && n < 2) {
                DecompileResults dr = ifc.decompileFunction(cf, 100, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 5000) { c = c.substring(0, 5000) + "\n...(truncated)"; }
                    out.println(c);
                }
                n++;
            }
        }
        out.println();

        // 3) the spawn-manager vtable 0x01E68A30 - slot layout + where the create slot is called
        out.println("=== spawn-manager vtable 0x01e68a30 ===");
        for (int i = 0; i < 16; i++) {
            long off = 0x01E68A30L + i * 4;
            int v = getInt(toAddr(off));
            Function cf = getFunctionContaining(toAddr(v & 0xFFFFFFFFL));
            out.println(String.format("  [%02d]+0x%02X: 0x%08X %s", i, i * 4, v, cf != null ? cf.getName() : ""));
        }
        out.println();

        // 4) refs to the vtable - who uses the spawn manager
        out.println("=== refs to 0x01e68a30 ===");
        for (Reference r : getReferencesTo(toAddr(0x01E68A30L))) {
            out.println("  from " + r.getFromAddress());
        }
        out.close();
    }
}
