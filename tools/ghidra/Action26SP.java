import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action26SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action26.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long hit = 0x00495A94L;
        Function wf = getFunctionContaining(toAddr(hit));
        out.println("=== the writer (fn containing 0x495a94): " + (wf != null ? wf.getEntryPoint() + " " + wf.getName() : "NONE") + " ===");
        if (wf != null) {
            DecompileResults dr = ifc.decompileFunction(wf, 150, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 6000) { c = c.substring(0, 6000) + "\n...(truncated)"; }
                out.println(c);
            }
            byte[] bb = new byte[160];
            if (currentProgram.getMemory().getBytes(wf.getEntryPoint(), bb) == 160) {
                out.println("--- bytes (160) ---");
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < 160; i++) {
                    sb.append(String.format("%02X", bb[i]));
                    if ((i + 1) % 16 == 0) { sb.append("\n"); } else { sb.append(" "); }
                }
                out.println(sb.toString());
            }
        }
        out.println();

        // callers of the writer function
        out.println("=== refs to writer " + (wf != null ? wf.getEntryPoint().toString() : "?") + " ===");
        int n = 0;
        for (Reference r : getReferencesTo(wf.getEntryPoint())) {
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + " in " + cf);
            if (++n > 20) { out.println("  ...(more)"); break; }
        }
        out.println();

        // decompile up to 6 caller functions
        int dc = 0;
        for (Reference r : getReferencesTo(wf.getEntryPoint())) {
            Function cf = getFunctionContaining(r.getFromAddress());
            if (cf != null && !cf.getEntryPoint().equals(wf.getEntryPoint()) && dc < 6) {
                dc++;
                DecompileResults dr = ifc.decompileFunction(cf, 150, monitor);
                out.println("=== caller " + cf.getEntryPoint() + " " + cf.getName() + " ===");
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 4500) { c = c.substring(0, 4500) + "\n...(truncated)"; }
                    out.println(c);
                }
                out.println();
            }
        }
        out.close();
    }
}
