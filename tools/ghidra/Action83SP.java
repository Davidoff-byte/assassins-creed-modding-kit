import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.address.Address;
import java.io.PrintWriter;

public class Action83SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action83.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        Function fn = getFunctionAt(toAddr(0x0052A4A0L));
        out.println("=== FUN_0052a4a0 (node ctor) ===");
        if (fn != null) {
            out.println("size: " + fn.getBody().getNumAddresses());
            DecompileResults dr = ifc.decompileFunction(fn, 200, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 14000) { c = c.substring(0, 14000) + "\n...(truncated)"; }
                out.println(c);
            }
        }
        out.close();
    }
}
