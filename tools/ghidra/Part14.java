import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.Symbol;
import java.io.PrintWriter;

public class Part14 extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_part14.txt", "UTF-8");
        Memory mem = currentProgram.getMemory();
        long[] vtables = { 0x01E7F568L, 0x02596100L, 0x01E65930L };
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        int decompCount = 0;
        for (long v : vtables) {
            out.println("=== refs to 0x" + Long.toHexString(v) + " ===");
            Symbol s = getSymbolAt(toAddr(v));
            if (s != null) out.println("  symbol: " + s.getName(true));
            int n = 0;
            for (Reference r : getReferencesTo(toAddr(v))) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + "  in " + cf);
                if (cf != null && n < 2 && decompCount < 4) {
                    n++; decompCount++;
                    DecompileResults dr = ifc.decompileFunction(cf, 120, monitor);
                    if (dr.getDecompiledFunction() != null) {
                        String c = dr.getDecompiledFunction().getC();
                        if (c.length() > 3000) c = c.substring(0, 3000) + "\n...(truncated)";
                        out.println("--- fn " + cf.getEntryPoint() + " ---");
                        out.println(c);
                    }
                }
                if (++n > 10) { out.println("  ..."); break; }
            }
            out.println();
        }
        out.close();
    }
}
