import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;
import java.util.*;

public class Grph14 extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_grph14.txt", "UTF-8");
        long[] ctors = { 0x00924a60L, 0x00934c60L };
        for (long c : ctors) {
            out.println("=== callers of 0x" + Long.toHexString(c) + " ===");
            int n = 0;
            for (Reference r : getReferencesTo(toAddr(c))) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + "  in " + cf);
                if (++n > 20) { out.println("  ..."); break; }
            }
            out.println();
        }
        // what does slot 0x54 of the "definition" object's sub-object look like? grab the vtable region refs
        // also: who refs the *destructor* neighbours -> class layouts
        long[] more = { 0x00922fb0L };
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        for (long m : more) {
            Function f = getFunctionContaining(toAddr(m));
            if (f == null) { try { disassemble(toAddr(m)); } catch (Exception e) {} f = createFunction(toAddr(m), null); }
            out.println("=== fn 0x" + Long.toHexString(m) + " " + (f != null ? f.getName() : "?") + " ===");
            if (f != null) {
                DecompileResults r = ifc.decompileFunction(f, 120, monitor);
                if (r.getDecompiledFunction() != null) {
                    String s = r.getDecompiledFunction().getC();
                    if (s.length() > 3000) s = s.substring(0, 3000) + "\n...(truncated)";
                    out.println(s);
                }
            }
            out.println();
        }
        out.close();
    }
}
