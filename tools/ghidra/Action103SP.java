import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.address.Address;
import java.io.PrintWriter;

public class Action103SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action103.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] addrs = { 0x005FAC60L, 0x00526590L, 0x00A2E820L, 0x005FD6F0L };
        for (long a : addrs) {
            Function fn = getFunctionAt(toAddr(a));
            out.println("=== 0x" + Long.toHexString(a) + (fn != null ? " " + fn.getName() + " size=" + fn.getBody().getNumAddresses() : " NO-FN") + " ===");
            if (fn == null) { out.println(); continue; }
            DecompileResults dr = ifc.decompileFunction(fn, 150, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 9000) { c = c.substring(0, 9000) + "\n...(truncated)"; }
                out.println(c);
            }
            out.println();
        }

        // what is around the API table entry 0x1e5782c?
        out.println("=== data around 0x01e57800 (the table referencing the spawn API) ===");
        for (long p = 0x01E577E0L; p < 0x01E57860L; p += 4) {
            int v = getInt(toAddr(p));
            long vv = v & 0xFFFFFFFFL;
            Function cf = getFunctionContaining(toAddr(vv));
            String extra = cf != null ? cf.getName() : "";
            if (vv > 0x1E00000L && vv < 0x2B00000L) {
                try {
                    StringBuilder sb = new StringBuilder();
                    for (int i = 0; i < 40; i++) {
                        byte b = getByte(toAddr(vv + i));
                        if (b == 0) break;
                        if (b < 32 || b > 126) { sb.setLength(0); break; }
                        sb.append((char) b);
                    }
                    if (sb.length() > 2) extra = "\"" + sb + "\"";
                } catch (Exception e) {}
            }
            out.println(String.format("  0x%08X: 0x%08X %s", p, v, extra));
        }
        out.close();
    }
}
