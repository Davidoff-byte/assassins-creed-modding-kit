import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

// Force-create + decompile BF SP task entry points that are only reached indirectly.
public class DecompBFSP3 extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] addrs = { 0x0063bbb0L, 0x00663390L, 0x006632c0L, 0x0070e800L, 0x00455240L };
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_decomp3.txt", "UTF-8");
        for (long a : addrs) {
            Address ad = toAddr(a);
            Function f = getFunctionAt(ad);
            if (f == null) {
                try {
                    disassemble(ad);
                } catch (Exception e) {
                    // already disassembled
                }
                f = createFunction(ad, null);
            }
            out.println("=== " + Long.toHexString(a) + (f != null ? " " + f.getName() : " STILL NOFUNC") + " ===");
            if (f != null) {
                DecompileResults r = ifc.decompileFunction(f, 120, monitor);
                if (r.getDecompiledFunction() != null) {
                    out.println(r.getDecompiledFunction().getC());
                } else {
                    out.println("(decompile failed)");
                }
            }
            out.println();
        }
        out.close();
    }
}
