import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class WeaponTypePath extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] decomp = {0x1414a6270L, 0x1420f3d20L, 0x141807200L, 0x1417137f0L, 0x14185e990L};
        long[] callersOf = {0x14185e990L, 0x1420f3d20L, 0x1414a6270L};
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\wtype_out.txt", "UTF-8");
        for (long t : decomp) {
            Address a = toAddr(t);
            Function f = getFunctionAt(a);
            out.println("==================================================");
            out.println("FUNCTION " + a + " name=" + (f != null ? f.getName() : "?"));
            if (f == null) {
                continue;
            }
            DecompileResults res = ifc.decompileFunction(f, 120, monitor);
            if (res != null && res.decompileCompleted() && res.getDecompiledFunction() != null) {
                out.println(res.getDecompiledFunction().getC());
            } else {
                out.println("  decompile failed");
            }
        }
        for (long t : callersOf) {
            Address a = toAddr(t);
            out.println("=== CALLERS of " + a);
            for (Reference r : getReferencesTo(a)) {
                Function f = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + "  in  " + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
            }
        }
        out.close();
        ifc.dispose();
    }
}
