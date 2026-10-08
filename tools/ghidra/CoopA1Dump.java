import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import java.io.PrintWriter;

// AccCoop A1: bytes for scan signatures + decompile of the position accessor chain.
public class CoopA1Dump extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] bytesTargets = {
            0x140352c10L, // active player index
            0x140346aa0L, // player object by index
            0x1400d8600L, // -> position struct
            0x1400d8590L, // -> sub-object
            0x14009dcd0L, // current object getter
        };
        long[] decompTargets = {
            0x1401a7a40L,
            0x1400d8600L,
            0x1402892d0L,
        };
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\coop_a1.txt", "UTF-8");
        for (long t : bytesTargets) {
            Address a = toAddr(t);
            Function f = getFunctionAt(a);
            out.println("=== BYTES " + a + " " + (f != null ? f.getName() : "?"));
            byte[] b = new byte[32];
            currentProgram.getMemory().getBytes(a, b);
            StringBuilder sb = new StringBuilder();
            for (byte x : b) sb.append(String.format("%02X ", x));
            out.println("BYTES32: " + sb.toString().trim());
        }
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        for (long t : decompTargets) {
            Address a = toAddr(t);
            Function f = getFunctionAt(a);
            out.println("==================================================");
            out.println("FUNCTION " + a + " " + (f != null ? f.getName() : "?"));
            if (f != null) {
                DecompileResults r = ifc.decompileFunction(f, 120, monitor);
                if (r != null && r.decompileCompleted() && r.getDecompiledFunction() != null) {
                    out.println(r.getDecompiledFunction().getC());
                }
            }
        }
        ifc.dispose();
        out.close();
    }
}
