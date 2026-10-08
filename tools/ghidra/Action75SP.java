import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.address.Address;
import java.io.PrintWriter;

public class Action75SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action75.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        // all functions in the job-system neighborhood
        FunctionIterator it = currentProgram.getFunctionManager().getFunctions(toAddr(0x00A39000L), true);
        int n = 0;
        while (it.hasNext() && n < 40) {
            Function f = it.next();
            long s = f.getEntryPoint().getOffset();
            if (s >= 0x00A3C000L) { break; }
            n++;
            out.println("=== " + f.getEntryPoint() + " " + f.getName() + " size=" + f.getBody().getNumAddresses() + " ===");
            DecompileResults dr = ifc.decompileFunction(f, 60, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 3000) { c = c.substring(0, 3000) + "\n...(truncated)"; }
                out.println(c);
            }
            out.println();
        }
        out.close();
    }
}
