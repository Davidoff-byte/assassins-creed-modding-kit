import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.Symbol;
import java.io.PrintWriter;

public class Query14b extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_q14b.txt", "UTF-8");
        Memory mem = currentProgram.getMemory();
        long[] addrs = { 0x01E4CE90L, 0x04DD5F8CL };
        for (long a : addrs) {
            Address ad = toAddr(a);
            out.println("=== 0x" + Long.toHexString(a) + " ===");
            Symbol s = getSymbolAt(ad);
            out.println("  symbol: " + (s != null ? s.getName(true) : "(none)"));
            out.println("  dwords around:");
            for (int off = -0x10; off <= 0x30; off += 4) {
                int v;
                try { v = mem.getInt(ad.add(off)); } catch (Exception e) { continue; }
                if (v == 0) continue;
                String note = "";
                long uv = v & 0xFFFFFFFFL;
                if (uv >= 0x400000 && uv < 0x2B00000) {
                    Symbol fs = getSymbolAt(toAddr(uv));
                    note = " -> " + (fs != null ? fs.getName(true) : "EXE+0x" + Long.toHexString(uv - 0x400000));
                }
                out.println("    +" + Integer.toHexString(off) + ": 0x" + String.format("%08X", v) + note);
            }
            out.println("  references:");
            for (Reference r : getReferencesTo(ad)) {
                out.println("    " + r.getFromAddress() + " " + r.getReferenceType() + "  in " + getFunctionContaining(r.getFromAddress()));
            }
        }
        out.close();
    }
}
