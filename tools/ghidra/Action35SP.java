import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.Symbol;
import java.io.PrintWriter;

public class Action35SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action35.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] targets = { 0x026FAEB0L /*SpawnPlayerParams*/, 0x026FAEC4L /*SpawnCharacterParams*/,
                           0x01E4A6C8L /*PlayerSpawnEvent*/, 0x01E54ED0L /*PlayerSpawnActivatorComponent*/ };
        int budget = 10;
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
        // the g_MainPlayerPosition global symbol + its readers
        out.println("=== symbol g_MainPlayerPosition ===");
        for (Symbol s : currentProgram.getSymbolTable().getSymbols("g_MainPlayerPosition")) {
            out.println("  " + s.getAddress() + " " + s.getName(true));
            int n = 0;
            for (Reference r : getReferencesTo(s.getAddress())) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("    read/write by " + r.getFromAddress() + " " + r.getReferenceType() + " in " + cf);
                if (++n > 12) { out.println("    ...(more)"); break; }
            }
        }
        out.close();
    }
}
