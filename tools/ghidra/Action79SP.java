import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action79SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action79.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] addrs = { 0x0073C190L, 0x00A33F00L, 0x00A1F160L, 0x00A47D70L };
        for (long a : addrs) {
            Function fn = getFunctionAt(toAddr(a));
            out.println("=== 0x" + Long.toHexString(a) + (fn != null ? " " + fn.getName() + " size=" + fn.getBody().getNumAddresses() : " NO-FN") + " ===");
            if (fn == null) { out.println(); continue; }
            DecompileResults dr = ifc.decompileFunction(fn, 200, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 9000) { c = c.substring(0, 9000) + "\n...(truncated)"; }
                out.println(c);
            }
            out.println();
        }

        // callers of the spawn-create (FUN_0073c190)
        out.println("=== callers of FUN_0073c190 (spawn create) ===");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(0x0073C190L))) {
            if (!r.getReferenceType().isCall()) { continue; }
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  from " + r.getFromAddress() + (cf != null ? " in " + cf.getName() : ""));
            if (cf != null && n < 2) {
                DecompileResults dr = ifc.decompileFunction(cf, 100, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 5000) { c = c.substring(0, 5000) + "\n...(truncated)"; }
                    out.println(c);
                }
                n++;
            }
            out.println();
        }
        out.close();
    }
}
