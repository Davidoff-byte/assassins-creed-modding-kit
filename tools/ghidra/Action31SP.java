import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action31SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action31.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] funcs = { 0x01AC1AD0L, 0x013AEC10L, 0x01AB5090L, 0x01AB5160L, 0x01AB5390L };
        for (long f : funcs) {
            Function cf = getFunctionAt(toAddr(f));
            out.println("=== 0x" + Long.toHexString(f) + " (" + (cf != null ? cf.getName() : "no-fn") + ") ===");
            if (cf != null) {
                DecompileResults dr = ifc.decompileFunction(cf, 150, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 5500) { c = c.substring(0, 5500) + "\n...(truncated)"; }
                    out.println(c);
                }
            }
            out.println();
        }

        out.println("=== refs to FUN_01ac1ad0 (who drives the action machine) ===");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(0x01AC1AD0L))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + " in " + cf);
            if (++n > 25) { out.println("  ...(more)"); break; }
        }
        out.close();
    }
}
