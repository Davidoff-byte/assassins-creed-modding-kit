import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action16MP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfmp_action16.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] funcs = {
            0x004D1BEDL, // EnterCustomActionState handler
            0x004CA815L, // ExitCustomActionState handler
            0x004BFCD3L  // SetMoveReplicationMode handler
        };
        for (long f : funcs) {
            Function cf = getFunctionAt(toAddr(f));
            out.println("=== handler 0x" + Long.toHexString(f) + " (" + (cf != null ? cf.getName() : "no-fn") + ") ===");
            if (cf != null) {
                DecompileResults dr = ifc.decompileFunction(cf, 150, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 5000) { c = c.substring(0, 5000) + "\n...(truncated)"; }
                    out.println(c);
                }
            }
            out.println();
        }

        // pointer slots referenced by the message descriptors
        long[] ptrSlots = { 0x0139A5DCL, 0x01399F74L, 0x0139A118L };
        for (long s : ptrSlots) {
            try {
                long fn = getInt(toAddr(s)) & 0xFFFFFFFFL;
                out.println("=== ptr slot 0x" + Long.toHexString(s) + " -> 0x" + Long.toHexString(fn) + " ===");
                Function cf = getFunctionAt(toAddr(fn));
                if (cf != null) {
                    DecompileResults dr = ifc.decompileFunction(cf, 150, monitor);
                    if (dr.getDecompiledFunction() != null) {
                        String c = dr.getDecompiledFunction().getC();
                        if (c.length() > 4000) { c = c.substring(0, 4000) + "\n...(truncated)"; }
                        out.println(c);
                    }
                } else {
                    out.println("  (not a known function)");
                }
            } catch (Exception e) {
                out.println("=== ptr slot 0x" + Long.toHexString(s) + " unreadable ===");
            }
            out.println();
        }

        // function containing the LAB the Enter descriptor points at
        long lab = 0x004D9140L;
        Function lf = getFunctionContaining(toAddr(lab));
        out.println("=== fn containing 0x" + Long.toHexString(lab) + ": " + (lf != null ? lf.getEntryPoint() : "none") + " ===");
        if (lf != null) {
            DecompileResults dr = ifc.decompileFunction(lf, 150, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 4000) { c = c.substring(0, 4000) + "\n...(truncated)"; }
                out.println(c);
            }
        }
        out.println();

        // senders: who references the Enter/Exit message descriptors
        long[] descs = { 0x01A1C838L, 0x01A1C850L };
        for (long d : descs) {
            out.println("=== refs to message descriptor 0x" + Long.toHexString(d) + " ===");
            int n = 0;
            int dc = 0;
            for (Reference r : getReferencesTo(toAddr(d))) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + "  in " + cf);
                if (cf != null && dc < 2) {
                    dc++;
                    DecompileResults dr = ifc.decompileFunction(cf, 150, monitor);
                    if (dr.getDecompiledFunction() != null) {
                        String c = dr.getDecompiledFunction().getC();
                        if (c.length() > 3500) { c = c.substring(0, 3500) + "\n...(truncated)"; }
                        out.println("--- fn " + cf.getEntryPoint() + " ---");
                        out.println(c);
                    }
                }
                if (++n > 20) { out.println("  ...(more)"); break; }
            }
            out.println();
        }
        out.close();
    }
}
