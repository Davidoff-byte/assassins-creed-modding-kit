import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;
import java.util.LinkedHashSet;
import java.util.Set;

public class Action34SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action34.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        Set<Function> fns = new LinkedHashSet<>();
        for (Reference r : getReferencesTo(toAddr(0x00A1C970L))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            if (cf != null) { fns.add(cf); }
        }
        out.println("=== " + fns.size() + " name-lookup callers ===");
        int shown = 0;
        for (Function cf : fns) {
            DecompileResults dr = ifc.decompileFunction(cf, 60, monitor);
            String c = dr.getDecompiledFunction() != null ? dr.getDecompiledFunction().getC() : "";
            // extract the string literal passed to the lookup
            String name = "";
            int i = c.indexOf("FUN_00a1c970(\"");
            if (i >= 0) {
                int j = c.indexOf('"', i + 14);
                if (j > i) { name = c.substring(i + 13, j); }
            }
            out.println(cf.getEntryPoint() + "  name=\"" + name + "\"  size=" + cf.getBody().getNumAddresses());
            if (name.isEmpty() && shown < 12) {
                shown++;
                String s = c.length() > 500 ? c.substring(0, 500) : c;
                out.println("  --- decompile snippet ---");
                out.println(s);
            }
        }
        out.close();
    }
}
