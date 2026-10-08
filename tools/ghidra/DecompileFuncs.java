import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

public class DecompileFuncs extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] targets = {
            0x141022070L, // "Stalking"
            0x1410234b0L, // "DualWield"
            0x14102e960L, // PerfectParry / Parry
            0x141ebc6e0L, // [Blend Action] Toggle Player Vanish
            0x1414a63c0L, // WeaponType_*HolsterPistol
            0x1416e1b60L  // Stalking Assassination / Counter Kill
        };
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\decomp_out.txt", "UTF-8");
        for (long t : targets) {
            Address a = toAddr(t);
            Function f = getFunctionAt(a);
            out.println("==================================================");
            out.println("FUNCTION " + a + " name=" + (f != null ? f.getName() : "?"));
            if (f == null) {
                out.println("  (no function)");
                continue;
            }
            DecompileResults res = ifc.decompileFunction(f, 90, monitor);
            if (res != null && res.decompileCompleted() && res.getDecompiledFunction() != null) {
                out.println(res.getDecompiledFunction().getC());
            } else {
                out.println("  decompile failed: " + (res != null ? res.getErrorMessage() : "null"));
            }
        }
        out.close();
        ifc.dispose();
    }
}
