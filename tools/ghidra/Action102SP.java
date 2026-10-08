import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action102SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action102.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] sites = { 0x5FD77AL, 0x602D35L };
        for (long s : sites) {
            Function fn = getFunctionContaining(toAddr(s));
            out.println("=== call site 0x" + Long.toHexString(s) + " in " +
                        (fn != null ? fn.getName() + " @" + fn.getEntryPoint() + " size=" + fn.getBody().getNumAddresses() : "NO-FN") + " ===");
            if (fn != null) {
                DecompileResults dr = ifc.decompileFunction(fn, 200, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 11000) { c = c.substring(0, 11000) + "\n...(truncated)"; }
                    out.println(c);
                }
                out.println("=== callers of " + fn.getEntryPoint() + " ===");
                for (Reference r : getReferencesTo(fn.getEntryPoint())) {
                    Function cf = getFunctionContaining(r.getFromAddress());
                    out.println("  from " + r.getFromAddress() + (cf != null ? " in " + cf.getName() + " @" + cf.getEntryPoint() : ""));
                }
            }
            out.println();
        }
        out.close();
    }
}
