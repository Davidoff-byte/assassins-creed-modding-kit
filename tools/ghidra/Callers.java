import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Callers extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] targets = {0x1410234b0L, 0x1417153e0L, 0x141022070L};
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\callers_out.txt", "UTF-8");
        for (long t : targets) {
            Address a = toAddr(t);
            out.println("=== CALLERS of " + a);
            for (Reference r : getReferencesTo(a)) {
                Function f = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + "  in  " + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
            }
        }
        // decompile the weapon-class getter
        Function g = getFunctionAt(toAddr(0x1417153e0L));
        out.println("=== DECOMPILE 1417153e0 ===");
        if (g != null) {
            DecompileResults res = ifc.decompileFunction(g, 90, monitor);
            if (res != null && res.decompileCompleted() && res.getDecompiledFunction() != null) {
                out.println(res.getDecompiledFunction().getC());
            } else {
                out.println("decompile failed");
            }
        }
        out.close();
        ifc.dispose();
    }
}
