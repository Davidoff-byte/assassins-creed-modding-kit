import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

public class Action108SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action108.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] sites = { 0x8A1F7EL, 0xA35A1EL, 0xA38111L, 0x503338L };
        for (long s : sites) {
            Function fn = getFunctionContaining(toAddr(s));
            out.println("=== site 0x" + Long.toHexString(s) + " in " +
                        (fn != null ? fn.getName() + " @" + fn.getEntryPoint() + " size=" + fn.getBody().getNumAddresses() : "NO-FN") + " ===");
            if (fn != null) {
                DecompileResults dr = ifc.decompileFunction(fn, 100, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 5000) { c = c.substring(0, 5000) + "\n...(truncated)"; }
                    out.println(c);
                }
            }
            out.println();
        }
        out.close();
    }
}
