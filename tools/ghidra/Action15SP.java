import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action15SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action15.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        long[] targets = {
            0x0268DB0CL, // CrowdLifeCustomActionEvent
            0x0268DAD0L, // CrowdLifeEndCustomActionEvent
            0x0268DE58L, // CustomAction
            0x0268A9D0L, // CustomActionPositionData
            0x02685E84L, // TransitionAnimationStateEvent
            0x02685E60L, // TransitionAnimationStateEventSeed
            0x026D1AB8L, // FreeRunTargetingMagnetComponent
            0x0270BB38L  // FreeRunCornerTurnComponent
        };
        for (long t : targets) {
            out.println("=== refs to 0x" + Long.toHexString(t) + " ===");
            int n = 0;
            int dc = 0;
            for (Reference r : getReferencesTo(toAddr(t))) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + "  in " + cf);
                if (cf != null && dc < 3) {
                    dc++;
                    DecompileResults dr = ifc.decompileFunction(cf, 120, monitor);
                    if (dr.getDecompiledFunction() != null) {
                        String c = dr.getDecompiledFunction().getC();
                        if (c.length() > 2800) { c = c.substring(0, 2800) + "\n...(truncated)"; }
                        out.println("--- fn " + cf.getEntryPoint() + " ---");
                        out.println(c);
                    }
                }
                if (++n > 14) { out.println("  ...(more)"); break; }
            }
            out.println();
        }
        out.close();
    }
}
