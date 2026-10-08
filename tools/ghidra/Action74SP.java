import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action74SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action74.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] addrs = { 0x00A2DBD0L, 0x005034B0L, 0x00527270L, 0x00A40BD0L, 0x00A2D4F0L };
        for (long a : addrs) {
            Function fn = getFunctionAt(toAddr(a));
            out.println("=== 0x" + Long.toHexString(a) + (fn != null ? " " + fn.getName() + " size=" + fn.getBody().getNumAddresses() : " NO-FN") + " ===");
            if (fn == null) { out.println(); continue; }
            DecompileResults dr = ifc.decompileFunction(fn, 120, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 7000) { c = c.substring(0, 7000) + "\n...(truncated)"; }
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

        // who references the queue DAT_027f6a44 (the job system's target queue)?
        out.println("=== refs to 0x027f6a44 (job queue) ===");
        for (Reference r : getReferencesTo(toAddr(0x027F6A44L))) {
            out.println("  from " + r.getFromAddress());
        }
        out.println();
        out.close();
    }
}
