import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Alloc14 extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_alloc14.txt", "UTF-8");
        long ctor = 0x0052a4a0L;
        out.println("=== callers of node ctor 0x" + Long.toHexString(ctor) + " ===");
        java.util.LinkedHashSet<Function> fns = new java.util.LinkedHashSet<>();
        for (Reference r : getReferencesTo(toAddr(ctor))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + "  in " + cf);
            if (cf != null) fns.add(cf);
        }
        out.println();
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        int n = 0;
        for (Function f : fns) {
            if (++n > 5) break;
            out.println("=== fn " + f.getEntryPoint() + " " + f.getName() + " ===");
            DecompileResults r = ifc.decompileFunction(f, 120, monitor);
            if (r.getDecompiledFunction() != null) {
                String c = r.getDecompiledFunction().getC();
                if (c.length() > 2800) c = c.substring(0, 2800) + "\n... (truncated)";
                out.println(c);
            }
            out.println();
        }
        out.close();
    }
}
