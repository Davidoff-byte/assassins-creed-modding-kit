import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Desc14 extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_desc14.txt", "UTF-8");
        long[] vtables = { 0x016A1640L, 0x0186B340L };
        long[] descs = { 0x026E34D8L, 0x026FA898L };
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        for (long vt : vtables) {
            out.println("=== vtable 0x" + Long.toHexString(vt) + " first 32 slots ===");
            for (int i = 0; i < 32; i++) {
                try {
                    long fn = getInt(toAddr(vt + i * 4L)) & 0xFFFFFFFFL;
                    if (fn < 0x400000L || fn > 0x2F00000L) { break; }
                    String nm = "";
                    Function f = getFunctionAt(toAddr(fn));
                    if (f != null) { nm = " " + f.getName(); }
                    out.println(String.format("  [%02d] 0x%08X%s", i, fn, nm));
                } catch (Exception e) { break; }
            }
            int dc = 0;
            for (Reference r : getReferencesTo(toAddr(vt))) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("  ref " + r.getFromAddress() + " " + r.getReferenceType() + " in " + cf);
                if (cf != null && dc < 2) {
                    dc++;
                    DecompileResults dr = ifc.decompileFunction(cf, 120, monitor);
                    if (dr.getDecompiledFunction() != null) {
                        String c = dr.getDecompiledFunction().getC();
                        if (c.length() > 3000) { c = c.substring(0, 3000) + "\n...(truncated)"; }
                        out.println("--- fn " + cf.getEntryPoint() + " ---");
                        out.println(c);
                    }
                }
            }
            out.println();
        }
        for (long d : descs) {
            out.println("=== refs to descriptor 0x" + Long.toHexString(d) + " ===");
            int n = 0;
            for (Reference r : getReferencesTo(toAddr(d))) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + " in " + cf);
                if (++n > 20) { out.println("  ...(more)"); break; }
            }
            out.println();
        }
        out.close();
    }
}
