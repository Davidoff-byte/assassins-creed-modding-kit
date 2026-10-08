import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action58SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action58.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        Function entry = getFunctionAt(toAddr(0xF199C6L));
        out.println("=== calls from the CRT entry ===");
        for (Reference r : getReferencesFrom(entry.getEntryPoint())) {
            if (!r.getReferenceType().isCall()) { continue; }
            Function cf = getFunctionAt(r.getToAddress());
            out.println("  -> " + r.getToAddress() + (cf != null ? " " + cf.getName() : ""));
            if (cf != null) {
                DecompileResults dr = ifc.decompileFunction(cf, 120, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    // find main() call inside the CRT startup
                    int i = c.indexOf("main");
                    String snippet = c;
                    if (c.length() > 5000) { snippet = c.substring(0, 5000) + "\n...(truncated)"; }
                    out.println(snippet);
                }
            }
            out.println();
        }
        out.close();
    }
}
