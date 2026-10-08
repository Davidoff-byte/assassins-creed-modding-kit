import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action32SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action32.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] strings = { 0x026E2820L /*BhvGenericNPC*/, 0x02686EF0L /*BhvAnimal*/ };
        int budget = 8;
        for (long s : strings) {
            out.println("=== refs to 0x" + Long.toHexString(s) + " ===");
            int n = 0;
            for (Reference r : getReferencesTo(toAddr(s))) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + " in " + cf);
                if (cf != null && budget > 0) {
                    budget--;
                    DecompileResults dr = ifc.decompileFunction(cf, 150, monitor);
                    out.println("--- fn " + cf.getEntryPoint() + " ---");
                    if (dr.getDecompiledFunction() != null) {
                        String c = dr.getDecompiledFunction().getC();
                        if (c.length() > 4500) { c = c.substring(0, 4500) + "\n...(truncated)"; }
                        out.println(c);
                    }
                }
                if (++n > 14) { out.println("  ...(more)"); break; }
            }
            out.println();
        }
        out.close();
    }
}
