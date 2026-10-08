import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action18MP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfmp_action18.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        // FUN_004c53a0: the helper the apply-forward calls 3x
        long f = 0x004C53A0L;
        Function cf = getFunctionAt(toAddr(f));
        out.println("=== FUN_004c53a0 (" + (cf != null ? cf.getName() : "no-fn") + ") ===");
        if (cf != null) {
            DecompileResults dr = ifc.decompileFunction(cf, 150, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 4000) { c = c.substring(0, 4000) + "\n...(truncated)"; }
                out.println(c);
            }
            // bytes
            byte[] bb = new byte[96];
            if (currentProgram.getMemory().getBytes(toAddr(f), bb) == 96) {
                out.println("--- FUN_004c53a0 bytes (96) ---");
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < 96; i++) {
                    sb.append(String.format("%02X", bb[i]));
                    if ((i + 1) % 16 == 0) { sb.append("\n"); } else { sb.append(" "); }
                }
                out.println(sb.toString());
            }
            // callers
            out.println("--- refs to FUN_004c53a0 ---");
            int n = 0;
            for (Reference r : getReferencesTo(toAddr(f))) {
                Function c2 = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + " in " + c2);
                if (++n > 30) { out.println("  ...(more)"); break; }
            }
        }
        out.close();
    }
}
