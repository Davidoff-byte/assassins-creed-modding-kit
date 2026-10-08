import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.address.Address;
import java.io.PrintWriter;

public class Action65SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action65.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        Function fn = getFunctionAt(toAddr(0x00463020L));
        out.println("=== FUN_00463020 (main loop candidate) ===");
        if (fn != null) {
            out.println("size: " + fn.getBody().getNumAddresses() + " bytes");
            DecompileResults dr = ifc.decompileFunction(fn, 200, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 15000) { c = c.substring(0, 15000) + "\n...(truncated)"; }
                out.println(c);
            }
            out.println("=== CALLs from FUN_00463020 into game code ===");
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
            out.println("=== back-edge jumps (loop structure) ===");
            var insns2 = currentProgram.getListing().getInstructions(fn.getBody(), true);
            while (insns2.hasNext()) {
                Instruction ins = insns2.next();
                String m = ins.getMnemonicString();
                if (!m.startsWith("J") || m.equals("JMP") || m.startsWith("JM") == false && (m.equals("JZ")||m.equals("JNZ")||m.equals("JA")||m.equals("JB")||m.equals("JG")||m.equals("JL")||m.equals("JS")||m.equals("JNS"))) {
                    // filter: any conditional jump
                }
                Address t = null;
                for (int i = 0; i < ins.getNumOperands(); i++) {
                    for (Object o : ins.getOpObjects(i)) {
                        if (o instanceof Address) { t = (Address) o; }
                    }
                }
                if (t != null && t.getOffset() < ins.getAddress().getOffset()) {
                    out.println("  " + ins.getAddress() + ": " + ins.toString() + " (back to " + t + ")");
                }
            }
        } else {
            out.println("no function at 0x00463020");
        }
        out.close();
    }
}
