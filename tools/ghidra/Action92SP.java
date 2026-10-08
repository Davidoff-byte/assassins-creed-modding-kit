import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import java.io.PrintWriter;

public class Action92SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action92.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        Function fn = getFunctionContaining(toAddr(0xF18057L));
        out.println("=== function containing 0xF18057 ===");
        if (fn != null) {
            out.println("entry: " + fn.getEntryPoint() + " " + fn.getName() + " size=" + fn.getBody().getNumAddresses());
            DecompileResults dr = ifc.decompileFunction(fn, 60, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 4000) { c = c.substring(0, 4000) + "\n...(truncated)"; }
                out.println(c);
            }
            out.println("=== first instructions ===");
            var insns = currentProgram.getListing().getInstructions(fn.getBody(), true);
            int n = 0;
            while (insns.hasNext() && n < 16) {
                out.println("  " + insns.next().toString());
                n++;
            }
            out.println("=== instructions around 0xF18057 ===");
            for (long a = 0xF18040L; a < 0xF18070L; ) {
                Instruction ins = getInstructionAt(toAddr(a));
                if (ins == null) { break; }
                out.println("  " + ins.toString());
                a = ins.getAddress().getOffset() + ins.getLength();
            }
        } else {
            out.println("no function (CRT region)");
        }
        out.close();
    }
}
