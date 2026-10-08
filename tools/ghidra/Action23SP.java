import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.List;

public class Action23SP extends GhidraScript {
    static class Pat { byte[] b; byte[] m; String label; }

    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action23.txt", "UTF-8");
        Memory mem = currentProgram.getMemory();
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        int[] regs = {0, 1, 2, 3, 6, 7}; // eax ecx edx ebx esi edi
        List<Pat> pats = new ArrayList<>();

        // (A) any-value word writes to +0x1D0
        for (int r : regs) {
            Pat p = new Pat();
            p.b = new byte[] {0x66, (byte)0xC7, (byte)(0x80 | r), (byte)0xD0, 0x01, 0, 0};
            p.m = new byte[] {(byte)0xFF, (byte)0xFF, (byte)0xFF, (byte)0xFF, (byte)0xFF, 0, 0};
            p.label = "w [r+" + r + "+0x1D0]=any";
            pats.add(p);
        }
        // (B) player-controller field writers (word + dword variants)
        int[][] offs = {{0xE0,0x00},{0x8D8,0x08},{0x8D4,0x08}};
        int[][] vals = {{0x2A,0x00},{0x07,0x00},{0x3F,0x00},{0xBC,0x00}};
        for (int r : regs) {
            for (int[] of : offs) {
                // dword writes: value matches one of the observed values
                for (int[] v : vals) {
                    Pat p = new Pat();
                    p.b = new byte[] {(byte)0xC7, (byte)(0x80 | r), (byte)of[0], (byte)of[1],
                                      (byte)v[0], 0, 0, 0};
                    p.m = new byte[] {(byte)0xFF, (byte)0xFF, (byte)0xFF, (byte)0xFF,
                                      (byte)0xFF, (byte)0xFF, (byte)0xFF, (byte)0xFF};
                    p.label = "d [r+" + r + "+0x" + Integer.toHexString(of[0]) + "]=0x" + Integer.toHexString(v[0]);
                    pats.add(p);
                }
                // word writes (value in low 16 bits, high word zero)
                for (int[] v : vals) {
                    Pat p = new Pat();
                    p.b = new byte[] {0x66, (byte)0xC7, (byte)(0x80 | r), (byte)of[0], (byte)of[1],
                                      (byte)v[0], 0};
                    p.m = new byte[] {(byte)0xFF, (byte)0xFF, (byte)0xFF, (byte)0xFF, (byte)0xFF,
                                      (byte)0xFF, (byte)0xFF};
                    p.label = "w [r+" + r + "+0x" + Integer.toHexString(of[0]) + "]=0x" + Integer.toHexString(v[0]);
                    pats.add(p);
                }
            }
            // or [reg+0x138], 1
            Pat p = new Pat();
            p.b = new byte[] {(byte)0x83, (byte)(0x88 | r), (byte)0x38, 0x01, 0x01};
            p.m = new byte[] {(byte)0xFF, (byte)0xFF, (byte)0xFF, (byte)0xFF, (byte)0xFF};
            p.label = "or [r+" + r + "+0x138],1";
            pats.add(p);
            // and [reg+0x138], 0xFE
            Pat q = new Pat();
            q.b = new byte[] {(byte)0x83, (byte)(0xA0 | r), (byte)0x38, 0x01, (byte)0xFE};
            q.m = new byte[] {(byte)0xFF, (byte)0xFF, (byte)0xFF, (byte)0xFF, (byte)0xFF};
            q.label = "and [r+" + r + "+0x138],0xFE";
            pats.add(q);
        }

        List<Long> hits = new ArrayList<>();
        for (Pat p : pats) {
            Address addr = toAddr(0x401000L);
            int h = 0;
            while (true) {
                addr = mem.findBytes(addr, p.b, p.m, true, monitor);
                if (addr == null) { break; }
                long v = addr.getOffset();
                if (!hits.contains(v)) {
                    hits.add(v);
                    out.println("HIT " + p.label + " @ " + addr);
                }
                h++;
                if (h > 4) { break; }
                addr = addr.add(1);
            }
        }
        out.println("=== total unique hits: " + hits.size() + " ===");
        int dc = 0;
        for (long h : hits) {
            Function cf = getFunctionContaining(toAddr(h));
            out.println("  hit " + toAddr(h) + " in " + cf);
            if (cf != null && dc < 10) {
                dc++;
                DecompileResults dr = ifc.decompileFunction(cf, 120, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 3500) { c = c.substring(0, 3500) + "\n...(truncated)"; }
                    out.println("--- fn " + cf.getEntryPoint() + " ---");
                    out.println(c);
                }
            }
        }
        out.close();
    }
}
