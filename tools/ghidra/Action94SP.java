import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.address.Address;
import java.io.PrintWriter;

public class Action94SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action94.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] addrs = { 0x00455240L, 0x00455310L };
        for (long a : addrs) {
            Function fn = getFunctionAt(toAddr(a));
            String label = (a == 0x455240L) ? "SpawningManagerUpdate1" : "SpawningManagerUpdate2";
            out.println("=== 0x" + Long.toHexString(a) + " " + label +
                        (fn != null ? " size=" + fn.getBody().getNumAddresses() : " NO-FN") + " ===");
            if (fn == null) { out.println(); continue; }
            DecompileResults dr = ifc.decompileFunction(fn, 250, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 16000) { c = c.substring(0, 16000) + "\n...(truncated)"; }
                out.println(c);
            }
            out.println("=== calls ===");
            var insns = currentProgram.getListing().getInstructions(fn.getBody(), true);
            int n = 0;
            while (insns.hasNext() && n < 30000) {
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
                    out.println("  " + ins.getAddress() + ": " + t + (cf != null ? " (" + cf.getName() + ")" : ""));
                }
            }
            out.println();
        }
        out.close();
    }
}
