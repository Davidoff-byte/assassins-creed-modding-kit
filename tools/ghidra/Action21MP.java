import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action21MP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfmp_action21.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] funcs = { 0x004BF85DL, 0x004BF899L, 0x004D92E9L };
        for (long f : funcs) {
            Function cf = getFunctionAt(toAddr(f));
            out.println("=== 0x" + Long.toHexString(f) + " (" + (cf != null ? cf.getName() : "no-fn") + ") ===");
            if (cf != null) {
                DecompileResults dr = ifc.decompileFunction(cf, 150, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 4500) { c = c.substring(0, 4500) + "\n...(truncated)"; }
                    out.println(c);
                }
                byte[] bb = new byte[128];
                if (currentProgram.getMemory().getBytes(toAddr(f), bb) == 128) {
                    out.println("--- bytes (128) ---");
                    StringBuilder sb = new StringBuilder();
                    for (int i = 0; i < 128; i++) {
                        sb.append(String.format("%02X", bb[i]));
                        if ((i + 1) % 16 == 0) { sb.append("\n"); } else { sb.append(" "); }
                    }
                    out.println(sb.toString());
                }
            }
            out.println();
        }
        // callers of the two core functions
        for (long f : new long[] { 0x004BF85DL, 0x004BF899L }) {
            out.println("=== refs to 0x" + Long.toHexString(f) + " ===");
            int n = 0;
            for (Reference r : getReferencesTo(toAddr(f))) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + " in " + cf);
                if (++n > 30) { out.println("  ...(more)"); break; }
            }
            out.println();
        }
        out.close();
    }
}
