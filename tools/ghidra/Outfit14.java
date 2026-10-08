import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Outfit14 extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_outfit14.txt", "UTF-8");
        long[] targets = { 0x026A9F80L, 0x026BD2ECL, 0x026DA1A0L, 0x026A9EECL, 0x026BCFB0L };
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        int decompCount = 0;
        for (long t : targets) {
            out.println("=== 0x" + Long.toHexString(t) + " ===");
            int n = 0;
            for (Reference r : getReferencesTo(toAddr(t))) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + "  in " + cf);
                if (cf != null && n < 2 && decompCount < 5) {
                    n++; decompCount++;
                    DecompileResults dr = ifc.decompileFunction(cf, 150, monitor);
                    if (dr.getDecompiledFunction() != null) {
                        String c = dr.getDecompiledFunction().getC();
                        if (c.length() > 3500) c = c.substring(0, 3500) + "\n...(truncated)";
                        out.println("--- fn " + cf.getEntryPoint() + " ---");
                        out.println(c);
                    }
                }
                if (++n > 12) { out.println("  ..."); break; }
            }
            out.println();
        }
        out.close();
    }
}
