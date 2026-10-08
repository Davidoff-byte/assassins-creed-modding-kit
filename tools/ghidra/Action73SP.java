import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.address.Address;
import java.io.PrintWriter;

public class Action73SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action73.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        // the sync clone + where FUN_00a2dae0 (job post) enters the chain
        long[] addrs = { 0x006DEFF0L, 0x00A38120L, 0x006DD8D0L, 0x00503600L, 0x0052A980L };
        for (long a : addrs) {
            Function fn = getFunctionAt(toAddr(a));
            out.println("=== 0x" + Long.toHexString(a) + (fn != null ? " " + fn.getName() + " size=" + fn.getBody().getNumAddresses() : " NO-FN") + " ===");
            if (fn == null) { out.println(); continue; }
            DecompileResults dr = ifc.decompileFunction(fn, 120, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 9000) { c = c.substring(0, 9000) + "\n...(truncated)"; }
                out.println(c);
            }
            var insns = currentProgram.getListing().getInstructions(fn.getBody(), true);
            StringBuilder calls = new StringBuilder("  calls: ");
            int n = 0;
            while (insns.hasNext() && n < 20000) {
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
                    calls.append(t.toString()).append(cf != null ? "(" + cf.getName() + ") " : " ");
                }
            }
            out.println(calls.toString());
            out.println();
        }
        out.close();
    }
}
