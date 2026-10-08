import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import java.io.PrintWriter;
import java.util.*;

public class Action27SP extends GhidraScript {
    static class Pat { byte[] b; byte[] m; int off; String form; }

    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action27.txt", "UTF-8");
        Memory mem = currentProgram.getMemory();
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        int[] offs = {0x8E0, 0x8D8, 0x8D4, 0x138, 0x8D0};
        List<Pat> pats = new ArrayList<>();
        for (int o : offs) {
            int lo = o & 0xFF, hi = (o >> 8) & 0xFF;
            for (int r = 0; r < 8; r++) {
                int modrm = 0x80 | r;
                pats.add(new Pat() {{ b = new byte[] {(byte)0xC7, (byte)modrm, (byte)lo, (byte)hi, 0,0,0,0};
                                     m = new byte[] {(byte)0xFF,(byte)0xFF,(byte)0xFF,(byte)0xFF,0,0,0,0};
                                     off = o; form = "dword-imm"; }});
                pats.add(new Pat() {{ b = new byte[] {0x66, (byte)0xC7, (byte)modrm, (byte)lo, (byte)hi, 0,0};
                                     m = new byte[] {(byte)0xFF,(byte)0xFF,(byte)0xFF,(byte)0xFF,(byte)0xFF,0,0};
                                     off = o; form = "word-imm"; }});
                pats.add(new Pat() {{ b = new byte[] {(byte)0xC6, (byte)modrm, (byte)lo, (byte)hi, 0};
                                     m = new byte[] {(byte)0xFF,(byte)0xFF,(byte)0xFF,(byte)0xFF,0};
                                     off = o; form = "byte-imm"; }});
                pats.add(new Pat() {{ b = new byte[] {(byte)0x89, (byte)modrm, (byte)lo, (byte)hi, 0,0,0};
                                     m = null; off = o; form = "mov-dword"; }});
                pats.add(new Pat() {{ b = new byte[] {0x66, (byte)0x89, (byte)modrm, (byte)lo, (byte)hi, 0,0,0};
                                     m = null; off = o; form = "mov-word"; }});
                pats.add(new Pat() {{ b = new byte[] {(byte)0x88, (byte)modrm, (byte)lo, (byte)hi, 0,0,0};
                                     m = null; off = o; form = "mov-byte"; }});
                pats.add(new Pat() {{ b = new byte[] {(byte)0xF3, 0x0F, 0x11, (byte)modrm, (byte)lo, (byte)hi, 0,0,0};
                                     m = null; off = o; form = "movss"; }});
                pats.add(new Pat() {{ b = new byte[] {0x0F, 0x29, (byte)modrm, (byte)lo, (byte)hi, 0,0,0};
                                     m = null; off = o; form = "movaps"; }});
            }
        }

        Map<Long, Function> hitFn = new LinkedHashMap<>();
        Map<Function, Set<Integer>> fnOffs = new HashMap<>();
        Map<Function, Set<String>> fnForms = new HashMap<>();
        for (Pat p : pats) {
            Address addr = toAddr(0x401000L);
            int per = 0;
            while (true) {
                addr = mem.findBytes(addr, p.b, p.m, true, monitor);
                if (addr == null) break;
                Function cf = getFunctionContaining(addr);
                if (cf != null) {
                    hitFn.putIfAbsent(addr.getOffset(), cf);
                    fnOffs.computeIfAbsent(cf, k -> new HashSet<>()).add(p.off);
                    fnForms.computeIfAbsent(cf, k -> new HashSet<>()).add(p.form);
                }
                if (++per > 3) break;
                addr = addr.add(1);
            }
        }
        // priority: functions touching 2+ offsets, then by address
        List<Function> cands = new ArrayList<>(fnOffs.keySet());
        cands.sort((a, b) -> {
            int sa = fnOffs.get(a).size(), sb = fnOffs.get(b).size();
            if (sa != sb) return sb - sa;
            return Long.compare(a.getEntryPoint().getOffset(), b.getEntryPoint().getOffset());
        });
        out.println("=== functions writing action offsets: " + cands.size() + " (sorted by offset coverage) ===");
        int dc = 0;
        for (Function cf : cands) {
            out.println("--- fn " + cf.getEntryPoint() + " offsets=" + fnOffs.get(cf) + " forms=" + fnForms.get(cf) + " ---");
            if (dc < 8) {
                dc++;
                DecompileResults dr = ifc.decompileFunction(cf, 120, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 3500) { c = c.substring(0, 3500) + "\n...(truncated)"; }
                    out.println(c);
                }
            }
        }
        out.close();
    }
}
