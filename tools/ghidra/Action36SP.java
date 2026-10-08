import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action36SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action36.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        out.println("=== refs to node vtable 0x01E4CE90 (ctor = who stores it) ===");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(0x01E4CE90L))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + " in " + cf);
            if (++n > 30) { out.println("  ...(more)"); break; }
        }
        out.println();

        // the known clone fn
        out.println("=== node clone FUN_0052a980 ===");
        Function cf2 = getFunctionAt(toAddr(0x0052A980L));
        if (cf2 != null) {
            DecompileResults dr = ifc.decompileFunction(cf2, 120, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 3500) { c = c.substring(0, 3500) + "\n...(truncated)"; }
                out.println(c);
            }
            out.println("=== refs to clone FUN_0052a980 ===");
            int m = 0;
            for (Reference r : getReferencesTo(cf2.getEntryPoint())) {
                Function c3 = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + " in " + c3);
                if (++m > 20) { out.println("  ...(more)"); break; }
            }
        }
        out.close();
    }
}
