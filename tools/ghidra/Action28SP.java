import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.Memory;
import java.io.PrintWriter;
import java.util.*;

public class Action28SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action28.txt", "UTF-8");
        Memory mem = currentProgram.getMemory();
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        int[][] dispBytes = {
            {0xE0, 0x08, 0x00, 0x00}, // 0x8E0
            {0xD8, 0x08, 0x00, 0x00}, // 0x8D8
            {0xD4, 0x08, 0x00, 0x00}, // 0x8D4
            {0x38, 0x01, 0x00, 0x00}, // 0x138
            {0xD0, 0x08, 0x00, 0x00}  // 0x8D0
        };
        int[] offVals = {0x8E0, 0x8D8, 0x8D4, 0x138, 0x8D0};

        Map<Long, Function> hitFn = new LinkedHashMap<>();
        Map<Function, Set<Integer>> fnOffs = new HashMap<>();
        Map<Function, List<String>> fnIns = new HashMap<>();
        int total = 0;
        for (int d = 0; d < dispBytes.length; d++) {
            byte[] pat = new byte[4];
            for (int i = 0; i < 4; i++) pat[i] = (byte) dispBytes[d][i];
            Address addr = toAddr(0x401000L);
            while (true) {
                addr = mem.findBytes(addr, pat, null, true, monitor);
                if (addr == null) break;
                long dispAddr = addr.getOffset();
                Instruction ins = getInstructionContaining(toAddr(dispAddr));
                boolean trailing = ins != null && ins.getAddress().add(ins.getLength() - 4).getOffset() == dispAddr;
                if (trailing) {
                    String s = ins.toString();
                    int br = s.indexOf(']');
                    int cm = s.indexOf(',');
                    if (br >= 0 && (cm < 0 || br < cm)) {
                        // memory is the destination => a WRITE
                        Function cf = getFunctionContaining(ins.getAddress());
                        if (cf != null) {
                            hitFn.putIfAbsent(ins.getAddress().getOffset(), cf);
                            fnOffs.computeIfAbsent(cf, k -> new HashSet<>()).add(offVals[d]);
                            fnIns.computeIfAbsent(cf, k -> new ArrayList<>()).add(ins.getAddress().toString() + " " + s);
                            total++;
                        }
                    }
                }
                addr = addr.add(1);
            }
        }
        out.println("=== total WRITE hits: " + total + " across " + fnOffs.size() + " functions ===");
        List<Function> cands = new ArrayList<>(fnOffs.keySet());
        cands.sort((a, b) -> {
            int sa = fnOffs.get(a).size(), sb = fnOffs.get(b).size();
            if (sa != sb) return sb - sa;
            return Long.compare(a.getEntryPoint().getOffset(), b.getEntryPoint().getOffset());
        });
        int dc = 0;
        for (Function cf : cands) {
            out.println("--- fn " + cf.getEntryPoint() + " offsets=" + fnOffs.get(cf) + " ---");
            for (String si : fnIns.get(cf)) { out.println("    " + si); }
            if (dc < 6) {
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
