// DecompileExec.java - decompile the native exec thunks to find the REAL vtable
// base and method addresses they dispatch to (the vtable-scan found static-init
// thunks instead). Exec thunks parse args then call *(vtable + offset).
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

public class DecompileExec extends GhidraScript {

    private static final long[] EXECS = {
        0x009EF0C0L, // execOnAddPower
        0x009EF120L, // execOnRemovePower
        0x009EF180L, // execOnMaxPowers
        0x009EF1E0L, // execOnMinPowers
        0x009EF480L, // execOnTogglePowerWheel
        0x009EF8A0L, // execOnCancelPlayerActivePower
        0x009EE630L, // execDis_SelectPower
        0x009EDBF0L, // execDis_StartPower
        0x009F32B0L, // execAddPower (CheatManager)
        0x009F4020L, // execBlinkShowRange
        0x009F4090L, // execBlinkShowRangeFull
    };

    @Override
    public void run() throws Exception {
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter(
            "C:\\Users\\Administrator\\ghidra_scripts\\exec_decomp_out.txt", "UTF-8");

        for (long a : EXECS) {
            Function f = getFunctionAt(toAddr(a));
            out.println("==================================================");
            out.println("EXEC " + toAddr(a) + (f != null ? " name=" + f.getName() : " (no func)"));
            if (f == null) {
                out.println("  (no function here)");
                out.println();
                continue;
            }
            DecompileResults res = ifc.decompileFunction(f, 120, monitor);
            if (res != null && res.decompileCompleted() && res.getDecompiledFunction() != null) {
                out.println(res.getDecompiledFunction().getC());
            } else {
                out.println("  decompile failed");
            }
            out.println();
        }

        out.close();
        ifc.dispose();
        println("DecompileExec done");
    }
}
