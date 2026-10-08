import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolIterator;
import ghidra.program.model.mem.Memory;
import java.io.PrintWriter;

public class DumpVT extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_vtable.txt", "UTF-8");
        long[] vt = { 0x02697010L, 0x02697074L };
        Memory mem = currentProgram.getMemory();
        for (long v : vt) {
            Address a = toAddr(v);
            out.println("=== at 0x" + Long.toHexString(v) + " ===");
            Symbol s = getSymbolAt(a);
            out.println("  symbol: " + (s != null ? s.getName(true) : "(none)"));
            out.println("  dwords around:");
            for (int off = -16; off <= 64; off += 4) {
                Address p = a.add(off);
                int val = mem.getInt(p);
                if (val == 0) continue;
                String note = "";
                long va = val & 0xFFFFFFFFL;
                if (va >= 0x400000 && va < 0x2B00000) {
                    Symbol fs = getSymbolAt(toAddr(va));
                    note = "  -> " + (fs != null ? fs.getName(true) : "EXE +0x"+Long.toHexString(va-0x400000));
                }
                out.println("    +" + (off>=0?"0x":"-0x") + Integer.toHexString(Math.abs(off)) + ": 0x" + String.format("%08X", val) + note);
            }
            out.println();
        }
        out.close();
    }
}
