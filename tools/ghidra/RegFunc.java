// RegFunc.java - the exe has a native-function registration table of
// { name-pointer, function-pointer } entries. Walk the region, resolve the
// name strings, and decompile the functions for Blink / Power entries.
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;
import java.util.LinkedHashMap;

public class RegFunc extends GhidraScript {

    private static final long LO = 0x012e4000L;
    private static final long HI = 0x012e5400L;

    private long readU32(Address a) {
        try {
            return currentProgram.getMemory().getInt(a) & 0xffffffffL;
        } catch (Exception e) {
            return -1;
        }
    }

    private String readCString(Address a) {
        try {
            Memory mem = currentProgram.getMemory();
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < 128; i++) {
                byte b = mem.getByte(a.add(i));
                if (b == 0) {
                    break;
                }
                sb.append((char) (b & 0xff));
            }
            return sb.toString();
        } catch (Exception e) {
            return null;
        }
    }

    @Override
    public void run() throws Exception {
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter(
            "C:\\Users\\Administrator\\ghidra_scripts\\regfunc_out.txt", "UTF-8");

        LinkedHashMap<Address, String> toDecomp = new LinkedHashMap<>();
        for (long off = LO; off < HI; off += 4) {
            Address a = toAddr(off);
            long v = readU32(a);
            if (v < 0x01000000L || v >= 0x01200000L) {
                continue;
            }
            String s = readCString(toAddr(v));
            if (s == null || s.isEmpty()) {
                continue;
            }
            long fn = readU32(a.add(4));
            String fnText = (fn >= 0x00400000L && fn < 0x01000000L)
                ? String.format("%08X", fn) : "-----";
            out.println(String.format("%08X  name=%s  fn=%s", off, s, fnText));
            if (fnText.length() == 8
                && (s.contains("Blink") || s.contains("Power") || s.contains("CancelPlayerActivePower"))) {
                toDecomp.put(toAddr(fn), s);
            }
        }

        out.println();
        out.println("=== decompiling " + toDecomp.size() + " entries ===");
        for (var e : toDecomp.entrySet()) {
            Address fa = e.getKey();
            Function f = getFunctionAt(fa);
            out.println("==================================================");
            out.println("FUNCTION " + fa + " for " + e.getValue()
                + (f != null ? "  name=" + f.getName() : "  (no function)"));
            if (f == null) {
                continue;
            }
            DecompileResults res = ifc.decompileFunction(f, 120, monitor);
            if (res != null && res.decompileCompleted() && res.getDecompiledFunction() != null) {
                out.println(res.getDecompiledFunction().getC());
            } else {
                out.println("  decompile failed");
            }
        }
        out.close();
        ifc.dispose();
        println("RegFunc done: " + toDecomp.size() + " to decompile");
    }
}
