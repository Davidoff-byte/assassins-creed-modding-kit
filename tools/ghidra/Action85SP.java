import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action85SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action85.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] addrs = { 0x0186B210L, 0x01863FD0L, 0x009F0AB0L, 0x0169B330L, 0x0186B340L };
        for (long a : addrs) {
            Function fn = getFunctionAt(toAddr(a));
            out.println("=== 0x" + Long.toHexString(a) + (fn != null ? " " + fn.getName() + " size=" + fn.getBody().getNumAddresses() : " NO-FN") + " ===");
            if (fn == null) { out.println(); continue; }
            DecompileResults dr = ifc.decompileFunction(fn, 150, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 8000) { c = c.substring(0, 8000) + "\n...(truncated)"; }
                out.println(c);
            }
            out.println();
        }
        out.close();
    }
}
