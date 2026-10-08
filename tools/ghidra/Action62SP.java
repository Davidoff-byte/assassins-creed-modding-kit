import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.address.Address;
import java.io.PrintWriter;

public class Action62SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action62.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        Function fn = getFunctionAt(toAddr(0x00405150L));
        out.println("=== FUN_00405150 (main loop?) decompile ===");
        if (fn != null) {
            out.println("size: " + fn.getBody().getNumAddresses() + " bytes");
            DecompileResults dr = ifc.decompileFunction(fn, 200, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 14000) { c = c.substring(0, 14000) + "\n...(truncated)"; }
                out.println(c);
            }
            out.println("=== CALLs from FUN_00405150 into game code ===");
            var insns = currentProgram.getListing().getInstructions(fn.getBody(), true);
            int n = 0;
            while (insns.hasNext() && n < 50000) {
                Instruction ins = insns.next();
                n++;
                if (!ins.getMnemonicString().equals("CALL")) { continue; }
                Address t = null;
                for (int i = 0; i < ins.getNumOperands(); i++) {
                    for (Object o : ins.getOpObjects(i)) {
                        if (o instanceof Address) { t = (Address) o; }
                    }
                }
                if (t == null) { continue; }
                long v = t.getOffset();
                if (v >= 0x400000L && v < 0x2F00000L) {
                    Function cf = getFunctionAt(t);
                    out.println("  " + ins.getAddress() + ": CALL " + t + (cf != null ? " (" + cf.getName() + ")" : ""));
                }
            }
        } else {
            out.println("no function at 0x00405150");
        }
        out.close();
    }
}
