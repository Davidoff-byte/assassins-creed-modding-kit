import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Skin14 extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_skin14.txt", "UTF-8");
        long desc = 0x02915CFCL;
        long vt = 0;
        try {
            vt = getInt(toAddr(desc)) & 0xFFFFFFFFL;
        } catch (Exception e) {
            out.println("read at desc failed: " + e);
        }
        out.println("class descriptor 0x" + Long.toHexString(desc) + " -> vtable 0x" + Long.toHexString(vt));
        out.println("--- vtable dwords (first 48) ---");
        for (int i = 0; i < 48; i++) {
            try {
                long fn = getInt(toAddr(vt + i * 4L)) & 0xFFFFFFFFL;
                if (fn < 0x400000L || fn > 0x2F00000L) { break; }
                String nm = "";
                Function f = getFunctionAt(toAddr(fn));
                if (f != null) { nm = " " + f.getName(); }
                out.println(String.format("  [%02d] 0x%08X%s", i, fn, nm));
            } catch (Exception e) {
                break;
            }
        }
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        long[] looks = { desc, vt };
        for (long t : looks) {
            out.println();
            out.println("=== refs to 0x" + Long.toHexString(t) + " ===");
            int n = 0;
            int dc = 0;
            for (Reference r : getReferencesTo(toAddr(t))) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + "  in " + cf);
                if (cf != null && dc < 6) {
                    dc++;
                    DecompileResults dr = ifc.decompileFunction(cf, 120, monitor);
                    if (dr.getDecompiledFunction() != null) {
                        String c = dr.getDecompiledFunction().getC();
                        if (c.length() > 2600) { c = c.substring(0, 2600) + "\n...(truncated)"; }
                        out.println("--- fn " + cf.getEntryPoint() + " ---");
                        out.println(c);
                    }
                }
                if (++n > 30) { out.println("  ...(more)"); break; }
            }
        }
        out.close();
    }
}
