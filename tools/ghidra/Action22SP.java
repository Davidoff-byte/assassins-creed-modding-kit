import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.List;

public class Action22SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action22.txt", "UTF-8");
        Memory mem = currentProgram.getMemory();
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        int[][] pats = {
            {0x66,0xC7,0x80,0xD0,0x01,0x00,0x00,0x01,0x01},
            {0x66,0xC7,0x81,0xD0,0x01,0x00,0x00,0x01,0x01},
            {0x66,0xC7,0x82,0xD0,0x01,0x00,0x00,0x01,0x01},
            {0x66,0xC7,0x83,0xD0,0x01,0x00,0x00,0x01,0x01},
            {0x66,0xC7,0x86,0xD0,0x01,0x00,0x00,0x01,0x01},
            {0x66,0xC7,0x87,0xD0,0x01,0x00,0x00,0x01,0x01},
            {0x66,0xC7,0x80,0xD0,0x01,0x00,0x00,0x01,0x00},
            {0x66,0xC7,0x81,0xD0,0x01,0x00,0x00,0x01,0x00},
            {0x66,0xC7,0x86,0xD0,0x01,0x00,0x00,0x01,0x00},
            {0x66,0xC7,0x87,0xD0,0x01,0x00,0x00,0x01,0x00},
            {0xC7,0x80,0xD0,0x01,0x00,0x00,0x01,0x01,0x00,0x00},
            {0xC7,0x81,0xD0,0x01,0x00,0x00,0x01,0x01,0x00,0x00},
            {0xC7,0x86,0xD0,0x01,0x00,0x00,0x01,0x01,0x00,0x00},
            {0xC7,0x87,0xD0,0x01,0x00,0x00,0x01,0x01,0x00,0x00}
        };

        List<Long> hits = new ArrayList<>();
        for (int[] p : pats) {
            byte[] bb = new byte[p.length];
            for (int i = 0; i < p.length; i++) { bb[i] = (byte) p[i]; }
            Address addr = toAddr(0x401000L);
            while (true) {
                addr = mem.findBytes(addr, bb, null, true, monitor);
                if (addr == null) { break; }
                long v = addr.getOffset();
                if (!hits.contains(v)) { hits.add(v); }
                addr = addr.add(1);
            }
        }
        out.println("=== SP hits for [reg+0x1D0] = 0x101 / 1 writes: " + hits.size() + " ===");
        int dc = 0;
        for (long h : hits) {
            Function cf = getFunctionContaining(toAddr(h));
            out.println("  " + toAddr(h) + " in " + cf);
            if (cf != null && dc < 8) {
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
