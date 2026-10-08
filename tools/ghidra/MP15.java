import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;
import java.util.*;

public class MP15 extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfmp_skin15.txt", "UTF-8");
        long[] strings = { 0x013A99ACL, 0x013ABD84L, 0x013ABD20L, 0x013ABE40L, 0x013C77BCL,
                           0x013A8168L, 0x013A8154L, 0x013AD1BCL, 0x013CA6F8L, 0x013C6A60L };
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        int decompCount = 0;
        for (long s : strings) {
            out.println("=== string @ 0x" + Long.toHexString(s) + " ===");
            int n = 0;
            for (Reference r : getReferencesTo(toAddr(s))) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + "  in " + cf);
                if (cf != null && n < 1 && decompCount < 7) {
                    n++; decompCount++;
                    DecompileResults dr = ifc.decompileFunction(cf, 120, monitor);
                    if (dr.getDecompiledFunction() != null) {
                        String c = dr.getDecompiledFunction().getC();
                        if (c.length() > 2500) c = c.substring(0, 2500) + "\n...(truncated)";
                        out.println("--- fn " + cf.getEntryPoint() + " ---");
                        out.println(c);
                    }
                }
            }
            out.println();
        }
        out.close();
    }
}
