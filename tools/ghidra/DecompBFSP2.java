import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

// Decompile BF SP per-frame task functions to find the camera manager + player path.
public class DecompBFSP2 extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] addrs = {
            0x0063bbb0L, // Ai::UpdateCamera
            0x006632c0L, // Ai::AIUpdate
            0x0065ddc0L, // Anim::UpdateDisplacement
            0x0071ba10L, // references FocusCameraManager
            0x0070e800L  // Ai::SpawningManagerUpdate (spawn path)
        };
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_decomp2.txt", "UTF-8");
        for (long a : addrs) {
            Address ad = toAddr(a);
            Function f = getFunctionAt(ad);
            if (f == null) {
                f = getFunctionContaining(ad);
            }
            out.println("=== " + Long.toHexString(a) + (f != null ? " " + f.getName() : " NOFUNC") + " ===");
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
