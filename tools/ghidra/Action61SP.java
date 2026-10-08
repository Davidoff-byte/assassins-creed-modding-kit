import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.address.Address;
import java.io.PrintWriter;

public class Action61SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action61.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        Function mainFn = getFunctionAt(toAddr(0x00406D10L));
        out.println("=== main() FUN_00406d10 decompile ===");
        if (mainFn != null) {
            DecompileResults dr = ifc.decompileFunction(mainFn, 200, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 12000) { c = c.substring(c.length() - 9000); }
                out.println(c);
            }
            // calls from main into game code
            out.println("=== CALLs from main into game code ===");
            var insns = currentProgram.getListing().getInstructions(mainFn.getBody(), true);
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
        }
        out.close();
    }
}
