// DecompileSlots.java - decompile the slot functions of vtable candidate
// 00fcae98 (the one whose slots are all real FUN_* in the 0x006xxxxx range).
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

public class DecompileSlots extends GhidraScript {
    private static final long[] FUNCS = {
        0x00650580L, // +0x788 OnAddPower
        0x00568fd0L, // +0x78c OnRemovePower
        0x0064af40L, // +0x798 OnMaxPowers
        0x006449d0L, // +0x79c OnMinPowers
        0x006a35b0L, // +0x7b8 OnTogglePowerWheel
        0x006a3630L, // +0x7e4 OnCancelPlayerActivePower
    };

    @Override
    public void run() throws Exception {
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter(
            "C:\\Users\\Administrator\\ghidra_scripts\\slots_decomp_out.txt", "UTF-8");

        for (long a : FUNCS) {
            Function f = getFunctionAt(toAddr(a));
            out.println("==================================================");
            out.println("FUNCTION " + toAddr(a) + (f != null ? " name=" + f.getName() : " (no func)"));
            if (f == null) { out.println("  (no function)"); out.println(); continue; }
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
        println("DecompileSlots done");
    }
}
