import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;
import java.util.*;

public class Fac15 extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_fac15.txt", "UTF-8");
        long target = 0x00900260L;
        out.println("=== callers of 0x" + Long.toHexString(target) + " (graphic factory wrapper) ===");
        LinkedHashSet<Function> fns = new LinkedHashSet<>();
        for (Reference r : getReferencesTo(toAddr(target))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + "  in " + cf);
            if (cf != null) fns.add(cf);
        }
        out.println();
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        int n = 0;
        for (Function f : fns) {
            if (++n > 4) break;
            out.println("=== fn " + f.getEntryPoint() + " " + f.getName() + " ===");
            DecompileResults r = ifc.decompileFunction(f, 150, monitor);
            if (r.getDecompiledFunction() != null) {
                String c = r.getDecompiledFunction().getC();
                if (c.length() > 4500) c = c.substring(0, 4500) + "\n... (truncated)";
                out.println(c);
            }
            out.println();
        }
        out.close();
    }
}
