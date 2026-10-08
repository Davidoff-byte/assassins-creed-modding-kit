import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

public class Desc14b extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_desc14b.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        long[] funcs = { 0x016A1640L, 0x016A1620L, 0x0186B210L, 0x01863FD0L };
        for (long f : funcs) {
            Function cf = getFunctionAt(toAddr(f));
            out.println("=== fn 0x" + Long.toHexString(f) + " (" + cf + ") ===");
            if (cf != null) {
                DecompileResults dr = ifc.decompileFunction(cf, 120, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 4000) { c = c.substring(0, 4000) + "\n...(truncated)"; }
                    out.println(c);
                }
            }
            out.println();
        }
        long[] descs = { 0x026E34D8L, 0x026FA898L };
        for (long d : descs) {
            out.println("=== descriptor 0x" + Long.toHexString(d) + " dwords ===");
            for (int i = 0; i < 16; i++) {
                try {
                    long v = getInt(toAddr(d + i * 4L)) & 0xFFFFFFFFL;
                    String extra = "";
                    if (v >= 0x400000L && v < 0x3000000L) {
                        var s = getSymbolAt(toAddr(v));
                        if (s != null) { extra = "  sym: " + s.getName(true); }
                        else { extra = String.format("  t0=0x%08X", getInt(toAddr(v)) & 0xFFFFFFFFL); }
                    } else if (v > 0x3000000L && v < 0x10000000L) {
                        extra = "  (heap/ptr?)";
                    }
                    out.println(String.format("  +0x%02X 0x%08X%s", i * 4, v, extra));
                } catch (Exception e) {
                    out.println("  +0x" + Integer.toHexString(i * 4) + " (unreadable)");
                }
            }
            out.println();
        }
        out.close();
    }
}
