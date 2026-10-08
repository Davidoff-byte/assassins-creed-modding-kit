import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action19MP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfmp_action19.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        // 1. the apply callback referenced by the Enter descriptor
        long lab = 0x004D9140L;
        Function lf = getFunctionAt(toAddr(lab));
        if (lf == null) { lf = createFunction(toAddr(lab), null); }
        out.println("=== LAB_004d9140 (Enter apply callback) ===");
        if (lf != null) {
            DecompileResults dr = ifc.decompileFunction(lf, 150, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 7000) { c = c.substring(0, 7000) + "\n...(truncated)"; }
                out.println(c);
            }
            byte[] bb = new byte[64];
            if (currentProgram.getMemory().getBytes(toAddr(lab), bb) == 64) {
                out.println("--- bytes (64) ---");
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < 64; i++) {
                    sb.append(String.format("%02X", bb[i]));
                    if ((i + 1) % 16 == 0) { sb.append("\n"); } else { sb.append(" "); }
                }
                out.println(sb.toString());
            }
        }
        out.println();

        // 2. payload readers + guards
        long[] funcs = { 0x004E7876L, 0x00404BC7L, 0x004E78D0L, 0x004D1AD1L, 0x004C5409L, 0x009A3391L };
        for (long f : funcs) {
            Function cf = getFunctionAt(toAddr(f));
            out.println("=== 0x" + Long.toHexString(f) + " (" + (cf != null ? cf.getName() : "no-fn") + ") ===");
            if (cf != null) {
                DecompileResults dr = ifc.decompileFunction(cf, 150, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 4500) { c = c.substring(0, 4500) + "\n...(truncated)"; }
                    out.println(c);
                }
            }
            out.println();
        }

        // 3. the payload class descriptor PTR_FUN_013864cc region
        out.println("=== class descriptor region @0x013864cc ===");
        for (int i = -4; i < 16; i++) {
            long a = 0x013864CCL + i * 4L;
            try {
                long v = getInt(toAddr(a)) & 0xFFFFFFFFL;
                String extra = "";
                if (v >= 0x400000L && v < 0x3000000L) {
                    var s = getSymbolAt(toAddr(v));
                    if (s != null) { extra = "  sym: " + s.getName(true); }
                }
                out.println(String.format("  +0x%02X 0x%08X%s", (i + 4) * 4, v, extra));
            } catch (Exception e) { }
        }
        out.println();
        out.println("=== refs to 0x013864cc ===");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(0x013864CCL))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + " in " + cf);
            if (++n > 20) { out.println("  ...(more)"); break; }
        }
        out.close();
    }
}
