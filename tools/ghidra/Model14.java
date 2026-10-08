import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.Symbol;
import java.io.PrintWriter;
import java.util.*;

public class Model14 extends GhidraScript {
    Memory mem;
    PrintWriter out;

    String strAt(long a) {
        try {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < 80; i++) {
                int b = mem.getByte(toAddr(a + i)) & 0xFF;
                if (b == 0) break;
                if (b < 32 || b > 126) return "";
                sb.append((char) b);
            }
            return sb.toString();
        } catch (Exception e) { return ""; }
    }

    @Override
    public void run() throws Exception {
        mem = currentProgram.getMemory();
        out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_model14.txt", "UTF-8");

        long[] targets = {
            0x02595BC8L, 0x02595050L,
            0x02595128L, 0x02595144L,
            0x027229ACL, 0x02725EE4L, 0x0271D4C4L,
            0x026BCFB0L, 0x026A9EECL,
            0x01E4CE90L
        };
        Set<Function> toDecomp = new LinkedHashSet<>();
        for (long t : targets) {
            String s = strAt(t);
            out.println("=== 0x" + Long.toHexString(t) + (s.isEmpty() ? "" : ("  \"" + s + "\"")) + " ===");
            Symbol sym = getSymbolAt(toAddr(t));
            if (sym != null) out.println("  sym: " + sym.getName(true));
            int n = 0;
            for (Reference r : getReferencesTo(toAddr(t))) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + "  in " + cf);
                if (cf != null && n < 8) { toDecomp.add(cf); }
                if (++n > 24) { out.println("  ..."); break; }
            }
            out.println();
        }

        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        int count = 0;
        for (Function f : toDecomp) {
            if (++count > 6) break;
            out.println("=== fn " + f.getEntryPoint() + " " + f.getName() + " ===");
            DecompileResults r = ifc.decompileFunction(f, 120, monitor);
            if (r.getDecompiledFunction() != null) {
                String c = r.getDecompiledFunction().getC();
                if (c.length() > 4000) c = c.substring(0, 4000) + "\n... (truncated)";
                out.println(c);
            } else out.println("(decompile failed)");
            out.println();
        }
        out.close();
    }
}
