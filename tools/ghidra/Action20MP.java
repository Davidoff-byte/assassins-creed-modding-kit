import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action20MP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfmp_action20.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] funcs = { 0x004C7566L, 0x0099B347L, 0x00D9B666L, 0x004C93E9L };
        for (long f : funcs) {
            Function cf = getFunctionAt(toAddr(f));
            out.println("=== 0x" + Long.toHexString(f) + " (" + (cf != null ? cf.getName() : "no-fn") + ") ===");
            if (cf != null) {
                DecompileResults dr = ifc.decompileFunction(cf, 150, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 5000) { c = c.substring(0, 5000) + "\n...(truncated)"; }
                    out.println(c);
                }
                byte[] bb = new byte[80];
                if (currentProgram.getMemory().getBytes(toAddr(f), bb) == 80) {
                    out.println("--- bytes (80) ---");
                    StringBuilder sb = new StringBuilder();
                    for (int i = 0; i < 80; i++) {
                        sb.append(String.format("%02X", bb[i]));
                        if ((i + 1) % 16 == 0) { sb.append("\n"); } else { sb.append(" "); }
                    }
                    out.println(sb.toString());
                }
            }
            out.println();
        }

        out.println("=== refs to FUN_004c7566 (who calls the action-apply) ===");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(0x004C7566L))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + " in " + cf);
            if (++n > 40) { out.println("  ...(more)"); break; }
        }
        out.close();
    }
}
