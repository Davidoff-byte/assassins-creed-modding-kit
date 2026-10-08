import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action89SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action89.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        out.println("=== refs to FUN_006defa0 (derived upgrade ctor) ===");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(0x006DEFA0L))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  from " + r.getFromAddress() + (cf != null ? " in " + cf.getName() : ""));
            if (cf != null && n < 3) {
                DecompileResults dr = ifc.decompileFunction(cf, 150, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 8000) { c = c.substring(0, 8000) + "\n...(truncated)"; }
                    out.println(c);
                }
                n++;
            }
        }
        out.close();
    }
}
