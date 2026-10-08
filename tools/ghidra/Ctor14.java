import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Ctor14 extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_ctor14.txt", "UTF-8");

        long[] ctorRefs = { 0x00526d90L, 0x0052a4a0L };
        for (long t : ctorRefs) {
            out.println("=== callers of 0x" + Long.toHexString(t) + " ===");
            int n = 0;
            for (Reference r : getReferencesTo(toAddr(t))) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + "  in " + cf);
                if (++n > 30) { out.println("  ..."); break; }
            }
            out.println();
        }

        long[] fns = { 0x0052a4a0L, 0x00526d90L, 0x0052a950L, 0x00529e70L, 0x0052a980L, 0x00507a20L, 0x0050ee30L };
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        for (long p : fns) {
            Address ad = toAddr(p);
            Function f = getFunctionContaining(ad);
            if (f == null) { try { disassemble(ad); } catch (Exception e) {} f = createFunction(ad, null); }
            out.println("=== fn 0x" + Long.toHexString(p) + "  " + (f != null ? (f.getEntryPoint() + " " + f.getName()) : "NOFUNC") + " ===");
            if (f != null) {
                DecompileResults r = ifc.decompileFunction(f, 120, monitor);
                if (r.getDecompiledFunction() != null) {
                    String c = r.getDecompiledFunction().getC();
                    if (c.length() > 3500) c = c.substring(0, 3500) + "\n... (truncated)";
                    out.println(c);
                } else out.println("(decompile failed)");
            }
            out.println();
        }
        out.close();
    }
}
