import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action104SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action104.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        // the function containing VA 0x17F3F8D
        Function fn = getFunctionContaining(toAddr(0x17F3F8DL));
        out.println("=== function containing 0x17f3f8d ===");
        if (fn != null) {
            out.println("entry: " + fn.getEntryPoint() + " " + fn.getName() + " size=" + fn.getBody().getNumAddresses());
            DecompileResults dr = ifc.decompileFunction(fn, 150, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 9000) { c = c.substring(0, 9000) + "\n...(truncated)"; }
                out.println(c);
            }
        }
        out.println();

        // who references the string g_EntityUniqueIDCol (0x1E46EF0)?
        out.println("=== refs to 0x01e46ef0 (g_EntityUniqueIDCol string) ===");
        for (Reference r : getReferencesTo(toAddr(0x01E46EF0L))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  from " + r.getFromAddress() + (cf != null ? " in " + cf.getName() + " @" + cf.getEntryPoint() : ""));
        }
        out.close();
    }
}
