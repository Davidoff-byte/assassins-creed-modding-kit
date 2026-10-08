import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action36MP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfmp_action36.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        out.println("=== callers of NetPlayer registration FUN_004fd528 ===");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(0x004FD528L))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + " in " + cf);
            if (++n > 20) { out.println("  ...(more)"); break; }
        }
        out.println();
        out.println("=== callers of the factory FUN_00c23e4e (object-class factory) ===");
        n = 0;
        for (Reference r : getReferencesTo(toAddr(0x00C23E4EL))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + " in " + cf);
            if (++n > 30) { out.println("  ...(more)"); break; }
        }
        out.close();
    }
}
