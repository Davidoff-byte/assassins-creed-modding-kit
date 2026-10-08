import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

public class DecompileMany extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] targets = {
            0x14171c250L, 0x14173ded0L, 0x1421d64f0L, 0x14181f690L, 0x14185e990L,
            0x141871270L, 0x1421ec270L, 0x142172510L, 0x142179760L, 0x142188020L,
            0x1421fb530L, 0x1414a6300L, 0x141339ac0L, 0x141e6bb10L, 0x1414a63c0L
        };
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\callers_decomp.txt", "UTF-8");
        for (long t : targets) {
            Address a = toAddr(t);
            Function f = getFunctionAt(a);
            out.println("==================================================");
            out.println("FUNCTION " + a + " name=" + (f != null ? f.getName() : "?"));
            if (f == null) {
                out.println("  (no function)");
                continue;
            }
            DecompileResults res = ifc.decompileFunction(f, 120, monitor);
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
