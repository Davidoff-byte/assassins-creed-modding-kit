import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import java.io.PrintWriter;

public class Action82SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action82.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        Function fn = getFunctionAt(toAddr(0x009F2E80L));
        out.println("=== FUN_009f2e80 (serializer init) ===");
        if (fn != null) {
            out.println("size: " + fn.getBody().getNumAddresses());
            // first 12 instructions (the crash is at +3)
            var insns = currentProgram.getListing().getInstructions(fn.getBody(), true);
            int n = 0;
            while (insns.hasNext() && n < 12) {
                out.println("  " + insns.next().toString());
                n++;
            }
            DecompileResults dr = ifc.decompileFunction(fn, 120, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 6000) { c = c.substring(0, 6000) + "\n...(truncated)"; }
                out.println(c);
            }
        } else {
            out.println("no function");
        }
        out.close();
    }
}
