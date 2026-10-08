import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action78SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action78.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        Function fn = getFunctionAt(toAddr(0x00A201A0L));
        out.println("=== FUN_00a201a0 (mass creator) ===");
        if (fn != null) {
            out.println("size: " + fn.getBody().getNumAddresses());
            DecompileResults dr = ifc.decompileFunction(fn, 300, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 12000) { c = c.substring(0, 12000) + "\n...(truncated)"; }
                out.println(c);
            }
        } else {
            out.println("no function at 0x00a201a0");
        }
        out.println();

        // callers - the real spawn sites with their invocation arguments
        out.println("=== callers of FUN_00a201a0 ===");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(0x00A201A0L))) {
            if (!r.getReferenceType().isCall()) { continue; }
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  from " + r.getFromAddress() + (cf != null ? " in " + cf.getName() : ""));
            if (cf != null && n < 3) {
                DecompileResults dr = ifc.decompileFunction(cf, 120, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 6000) { c = c.substring(0, 6000) + "\n...(truncated)"; }
                    out.println(c);
                }
                n++;
            }
            out.println();
        }
        out.close();
    }
}
