import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action86SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action86.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] addrs = { 0x00A51360L, 0x00A53540L, 0x00A5B4F0L };
        for (long a : addrs) {
            Function fn = getFunctionAt(toAddr(a));
            out.println("=== 0x" + Long.toHexString(a) + (fn != null ? " " + fn.getName() + " size=" + fn.getBody().getNumAddresses() : " NO-FN") + " ===");
            if (fn == null) { out.println(); continue; }
            DecompileResults dr = ifc.decompileFunction(fn, 150, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 8000) { c = c.substring(0, 8000) + "\n...(truncated)"; }
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

        // how does the engine find a managed object by type name/hash?
        out.println("=== refs to the \"ManagedObject\" string + registry entry points ===");
        for (long a : new long[]{0x00A51360L}) {
            out.println("  (see FUN_00a51360 refs below)");
        }
        for (Reference r : getReferencesTo(toAddr(0x00A51360L))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  call from " + r.getFromAddress() + (cf != null ? " in " + cf.getName() : ""));
        }
        out.close();
    }
}
