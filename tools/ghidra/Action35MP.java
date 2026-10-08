import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action35MP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfmp_action35.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] targets = { 0x013A5450L /*SpawnPlayerParams*/, 0x0139BE68L /*NetPlayer*/ };
        int budget = 8;
        for (long t : targets) {
            out.println("=== refs to 0x" + Long.toHexString(t) + " ===");
            int n = 0;
            for (Reference r : getReferencesTo(toAddr(t))) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + " in " + cf);
                if (cf != null && budget > 0) {
                    budget--;
                    DecompileResults dr = ifc.decompileFunction(cf, 120, monitor);
                    out.println("--- fn " + cf.getEntryPoint() + " ---");
                    if (dr.getDecompiledFunction() != null) {
                        String c = dr.getDecompiledFunction().getC();
                        if (c.length() > 3500) { c = c.substring(0, 3500) + "\n...(truncated)"; }
                        out.println(c);
                    }
                }
                if (++n > 12) { out.println("  ...(more)"); break; }
            }
            out.println();
        }
        out.close();
    }
}
