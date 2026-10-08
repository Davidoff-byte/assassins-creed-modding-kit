import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action99SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action99.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        // who calls the AI-phase registrar FUN_00663590? (that caller holds the world manager)
        out.println("=== refs to FUN_00663590 ===");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(0x00663590L))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  from " + r.getFromAddress() + (cf != null ? " in " + cf.getName() + " @" + cf.getEntryPoint() : ""));
            if (cf != null && n < 2) {
                DecompileResults dr = ifc.decompileFunction(cf, 200, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 10000) { c = c.substring(0, 10000) + "\n...(truncated)"; }
                    out.println(c);
                }
                n++;
            }
        }
        out.close();
    }
}
