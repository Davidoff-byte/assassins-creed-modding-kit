import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.Memory;
import java.io.PrintWriter;
import java.util.*;

public class Action29SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action29.txt", "UTF-8");
        Memory mem = currentProgram.getMemory();
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        int[][] dispBytes = {
            {0xE0, 0x08, 0x00, 0x00}, {0xD8, 0x08, 0x00, 0x00}, {0xD4, 0x08, 0x00, 0x00},
            {0x38, 0x01, 0x00, 0x00}, {0xD0, 0x08, 0x00, 0x00}
        };
        String[] names = {"0x8E0", "0x8D8", "0x8D4", "0x138", "0x8D0"};
        Map<Long, Function> fn = new LinkedHashMap<>();
        Map<Function, Set<String>> what = new HashMap<>();
        for (int d = 0; d < dispBytes.length; d++) {
            // LEA reg,[base+off]: mod=10, dest reg in bits 3-5, base in bits 0-2 -> enumerate both
            for (int dreg = 0; dreg < 8; dreg++) {
                for (int breg = 0; breg < 8; breg++) {
                    byte[] pat = {(byte)0x8D, (byte)(0x80 | (dreg << 3) | breg),
                                  (byte)dispBytes[d][0], (byte)dispBytes[d][1],
                                  (byte)dispBytes[d][2], (byte)dispBytes[d][3]};
                    Address addr = toAddr(0x401000L);
                    int n = 0;
                    while (true) {
                        addr = mem.findBytes(addr, pat, null, true, monitor);
                        if (addr == null) break;
                        Instruction ins = getInstructionAt(addr);
                        Function cf = ins != null ? getFunctionContaining(ins.getAddress()) : null;
                        if (cf != null) {
                            fn.putIfAbsent(ins.getAddress().getOffset(), cf);
                            what.computeIfAbsent(cf, k -> new HashSet<String>()).add(names[d]);
                        }
                        if (++n > 60) break;
                        addr = addr.add(1);
                    }
                }
            }
        }
        out.println("=== functions with LEA [reg+0x8xx]: " + fn.size() + " ===");
        List<Function> cands = new ArrayList<>(new HashSet<>(fn.values()));
        cands.sort((a, b) -> {
            int sa = what.get(a).size(), sb = what.get(b).size();
            if (sa != sb) return sb - sa;
            return Long.compare(a.getEntryPoint().getOffset(), b.getEntryPoint().getOffset());
        });
        int dc = 0;
        for (Function cf : cands) {
            out.println("--- fn " + cf.getEntryPoint() + " lea-offsets=" + what.get(cf) + " ---");
            if (dc < 8) {
                dc++;
                DecompileResults dr = ifc.decompileFunction(cf, 120, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 3000) { c = c.substring(0, 3000) + "\n...(truncated)"; }
                    out.println(c);
                }
            }
        }
        out.close();
    }
}
