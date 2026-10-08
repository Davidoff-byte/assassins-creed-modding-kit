import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

public class Pick14 extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_pick14.txt", "UTF-8");
        long[] fns = { 0x00963600L, 0x00934ce0L, 0x0085f9c0L };
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        for (long p : fns) {
            Address ad = toAddr(p);
            Function f = getFunctionContaining(ad);
            if (f == null) { try { disassemble(ad); } catch (Exception e) {} f = createFunction(ad, null); }
            out.println("=== fn 0x" + Long.toHexString(p) + "  " + (f != null ? (f.getEntryPoint() + " " + f.getName()) : "NOFUNC") + " ===");
            if (f != null) {
                DecompileResults r = ifc.decompileFunction(f, 180, monitor);
                if (r.getDecompiledFunction() != null) {
                    String c = r.getDecompiledFunction().getC();
                    if (c.length() > 6000) c = c.substring(0, 6000) + "\n... (truncated)";
                    out.println(c);
                } else out.println("(decompile failed)");
            }
            out.println();
        }
        out.close();
    }
}
