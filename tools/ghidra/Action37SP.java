import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action37SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action37.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] callers = { 0xA35A1EL, 0xA38111L, 0x503338L, 0x73C1D0L };
        for (long c : callers) {
            Function cf = getFunctionContaining(toAddr(c));
            out.println("=== caller 0x" + Long.toHexString(c) + " in fn " + (cf != null ? cf.getEntryPoint() + " " + cf.getName() : "NONE") + " ===");
            if (cf != null) {
                DecompileResults dr = ifc.decompileFunction(cf, 150, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String d = dr.getDecompiledFunction().getC();
                    if (d.length() > 5000) { d = d.substring(0, 5000) + "\n...(truncated)"; }
                    out.println(d);
                }
                out.println("--- refs to " + cf.getEntryPoint() + " ---");
                int n = 0;
                for (Reference r : getReferencesTo(cf.getEntryPoint())) {
                    Function c2 = getFunctionContaining(r.getFromAddress());
                    out.println("  " + r.getFromAddress() + " in " + c2);
                    if (++n > 15) { out.println("  ...(more)"); break; }
                }
            }
            out.println();
        }
        out.close();
    }
}
