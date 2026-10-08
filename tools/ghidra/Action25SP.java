import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import java.io.PrintWriter;
import java.util.*;

public class Action25SP extends GhidraScript {
    static class Pat { byte[] b; byte[] m; int off; }

    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action25.txt", "UTF-8");
        Memory mem = currentProgram.getMemory();
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        int[] offs = {0x0E0, 0x8D4, 0x8D8, 0x138, 0x8D0};
        List<Pat> pats = new ArrayList<>();
        for (int o : offs) {
            int lo = o & 0xFF, hi = (o >> 8) & 0xFF;
            for (int r = 0; r < 8; r++) {
                Pat p1 = new Pat();
                p1.b = new byte[] {(byte)0x89, (byte)(0x80|r), (byte)lo, (byte)hi, 0, 0, 0};
                p1.m = null; p1.off = o; pats.add(p1);
                Pat p2 = new Pat();
                p2.b = new byte[] {0x66, (byte)0x89, (byte)(0x80|r), (byte)lo, (byte)hi, 0, 0, 0};
                p2.m = null; p2.off = o; pats.add(p2);
                Pat p3 = new Pat();
                p3.b = new byte[] {(byte)0x88, (byte)(0x80|r), (byte)lo, (byte)hi, 0, 0, 0};
                p3.m = null; p3.off = o; pats.add(p3);
                Pat p4 = new Pat();
                p4.b = new byte[] {0x66, (byte)0xC7, (byte)(0x80|r), (byte)lo, (byte)hi, 0, 0};
                p4.m = new byte[] {(byte)0xFF,(byte)0xFF,(byte)0xFF,(byte)0xFF,(byte)0xFF,0,0};
                p4.off = o; pats.add(p4);
                Pat p5 = new Pat();
                p5.b = new byte[] {(byte)0xC7, (byte)(0x80|r), (byte)lo, (byte)hi, 0, 0, 0, 0};
                p5.m = new byte[] {(byte)0xFF,(byte)0xFF,(byte)0xFF,(byte)0xFF,0,0,0,0};
                p5.off = o; pats.add(p5);
            }
        }

        // hit -> function entry; function -> set of distinct offsets
        Map<Long, Function> hitFn = new LinkedHashMap<>();
        Map<Function, Set<Integer>> fnOffs = new HashMap<>();
        for (Pat p : pats) {
            Address addr = toAddr(0x401000L);
            while (true) {
                addr = mem.findBytes(addr, p.b, p.m, true, monitor);
                if (addr == null) { break; }
                Function cf = getFunctionContaining(addr);
                if (cf != null) {
                    hitFn.putIfAbsent(addr.getOffset(), cf);
                    fnOffs.computeIfAbsent(cf, k -> new HashSet<>()).add(p.off);
                }
                addr = addr.add(1);
            }
        }

        // functions touching >= 2 distinct action offsets
        List<Function> candidates = new ArrayList<>();
        for (Map.Entry<Function, Set<Integer>> e : fnOffs.entrySet()) {
            if (e.getValue().size() >= 2) { candidates.add(e.getKey()); }
        }
        candidates.sort(Comparator.comparing(f -> f.getEntryPoint().getOffset()));
        out.println("=== SP functions touching >=2 action offsets: " + candidates.size() + " ===");
        int dc = 0;
        for (Function cf : candidates) {
            out.println("--- fn " + cf.getEntryPoint() + " offsets=" + fnOffs.get(cf) + " ---");
            if (dc < 6) {
                dc++;
                DecompileResults dr = ifc.decompileFunction(cf, 120, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 4000) { c = c.substring(0, 4000) + "\n...(truncated)"; }
                    out.println(c);
                }
            }
        }
        out.close();
    }
}
