import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action54SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action54.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] funcs = { 0x00407390L, 0x00407410L, 0x00407200L };
        for (long f : funcs) {
            Function cf = getFunctionAt(toAddr(f));
            out.println("=== 0x" + Long.toHexString(f) + " (" + (cf != null ? cf.getName() : "no-fn") + ") ===");
            if (cf != null) {
                DecompileResults dr = ifc.decompileFunction(cf, 150, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 4000) { c = c.substring(0, 4000) + "\n...(truncated)"; }
                    out.println(c);
                }
                out.println("--- refs to " + cf.getEntryPoint() + " ---");
                int n = 0;
                for (Reference r : getReferencesTo(cf.getEntryPoint())) {
                    Function c2 = getFunctionContaining(r.getFromAddress());
                    out.println("  " + r.getFromAddress() + " in " + c2);
                    if (++n > 12) { out.println("  ...(more)"); break; }
                }
            }
            out.println();
        }
        out.close();
    }
}
