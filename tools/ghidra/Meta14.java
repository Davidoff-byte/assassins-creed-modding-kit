import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Symbol;
import java.io.PrintWriter;

public class Meta14 extends GhidraScript {
    Memory mem;
    PrintWriter out;

    String readCStr(long addr, int max) {
        try {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < max; i++) {
                int b = mem.getByte(toAddr(addr + i)) & 0xFF;
                if (b == 0) break;
                if (b < 9 || (b > 13 && b < 32) || b > 126) return "";
                sb.append((char) b);
            }
            return sb.toString();
        } catch (Exception e) { return ""; }
    }

    void dump(long addr, int before, int after) {
        out.println("=== 0x" + Long.toHexString(addr) + " ===");
        for (int off = -before; off <= after; off += 4) {
            int v;
            try { v = mem.getInt(toAddr(addr + off)); } catch (Exception e) { continue; }
            long uv = v & 0xFFFFFFFFL;
            String note = "";
            if (uv > 0x10000) {
                String s = readCStr(uv, 80);
                if (s.length() > 2) note = "  -> \"" + s + "\"";
                else {
                    Symbol sym = getSymbolAt(toAddr(uv));
                    if (sym != null) note = "  -> " + sym.getName(true);
                }
            }
            out.println("   +" + (off >= 0 ? "0x" : "-0x") + Integer.toHexString(Math.abs(off)) +
                        ": 0x" + String.format("%08X", v) + note);
        }
        out.println();
    }

    @Override
    public void run() throws Exception {
        mem = currentProgram.getMemory();
        out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_meta14.txt", "UTF-8");
        dump(0x0275E670L, 0x10, 0x40);
        dump(0x0275E4B4L, 0x10, 0x30);
        dump(0x027F6A3CL, 0x10, 0x30);
        dump(0x027F6A44L, 0x10, 0x30);
        dump(0x04DD5F8CL, 0x10, 0x30);
        out.close();
    }
}
