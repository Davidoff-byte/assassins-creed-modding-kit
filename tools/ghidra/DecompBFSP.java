import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

// Decompile BF SP (AC4BFSP.exe) engine anchors: task registrars + camera.
public class DecompBFSP extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] addrs = {
            0x00470b00L, // engine-frame task registrar (Ai::UpdateCamera, Engine::BeginFrame...)
            0x00663590L, // AI-world registrar (Ai::AIUpdate, Ai::SpawningManagerUpdate...)
            0x005863d0L, // references Anim::UpdateDisplacement
            0x0071ba10L  // references FocusCameraManager
        };
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_decomp.txt", "UTF-8");
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
