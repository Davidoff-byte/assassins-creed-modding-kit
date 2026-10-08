import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action88SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action88.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        // who calls the async clone FUN_006def40 (vtable+0x8)?
        out.println("=== refs to FUN_006def40 (async clone) ===");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(0x006DEF40L))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  from " + r.getFromAddress() + (cf != null ? " in " + cf.getName() : ""));
            if (cf != null && n < 2) {
                DecompileResults dr = ifc.decompileFunction(cf, 120, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 6000) { c = c.substring(0, 6000) + "\n...(truncated)"; }
                    out.println(c);
                }
                n++;
            }
        }
        out.println();

        // the derived ctor - does it set +4?
        Function ctor = getFunctionAt(toAddr(0x006DEFA0L));
        out.println("=== 0x6defa0 (derived ctor) ===");
        if (ctor != null) {
            DecompileResults dr = ifc.decompileFunction(ctor, 120, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 6000) { c = c.substring(0, 6000) + "\n...(truncated)"; }
                out.println(c);
            }
        }
        out.close();
    }
}
