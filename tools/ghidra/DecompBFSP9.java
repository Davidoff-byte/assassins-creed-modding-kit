import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

public class DecompBFSP9 extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] addrs = { 0x00417650L, 0x0040be50L, 0x00413c00L };
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_campos_writer.txt", "UTF-8");
        for (long a : addrs) {
            Address ad = toAddr(a);
            Function f = getFunctionAt(ad);
            if (f == null) { try { disassemble(ad); } catch (Exception e) {} f = createFunction(ad, null); }
            out.println("=== " + Long.toHexString(a) + (f != null ? " " + f.getName() : " NOFUNC") + " ===");
            if (f != null) {
                DecompileResults r = ifc.decompileFunction(f, 180, monitor);
                if (r.getDecompiledFunction() != null) out.println(r.getDecompiledFunction().getC());
                else out.println("(decompile failed)");
            }
            out.println();
        }
        out.close();
    }
}
