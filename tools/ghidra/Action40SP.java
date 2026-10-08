import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action40SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action40.txt", "UTF-8");
        Memory mem = currentProgram.getMemory();

        long[][] pats = {
            {0x0279A418L, 0x18, 0xA4, 0x79, 0x02}, // descriptor (class 0x01E64680)
            {0x0275CD58L, 0x58, 0xCD, 0x75, 0x02}, // descriptor (class 0x01E4A128)
            {0x01E68AF4L, 0xF4, 0x8A, 0xE6, 0x01}, // vtable slot FUN_0073c190
        };
        for (long[] p : pats) {
            long val = p[0];
            byte[] bb = {(byte) p[1], (byte) p[2], (byte) p[3], (byte) p[4]};
            out.println("=== who points at 0x" + Long.toHexString(val) + " ===");
            Address addr = toAddr(0x400000L);
            int n = 0;
            while (true) {
                addr = mem.findBytes(addr, bb, null, true, monitor);
                if (addr == null) break;
                long a = addr.getOffset();
                StringBuilder ctx = new StringBuilder();
                for (int i = -8; i <= 4; i++) {
                    try {
                        ctx.append(String.format(" %08X", getInt(toAddr(a + i * 4L)) & 0xFFFFFFFFL));
                    } catch (Exception e) { ctx.append(" ????????"); }
                }
                Function f = getFunctionAt(toAddr(a));
                var sym = getSymbolAt(toAddr(a));
                out.println("  @" + addr + (f != null ? " (fn " + f.getName() + ")" : sym != null ? " (sym " + sym.getName(true) + ")" : "") + ":" + ctx.toString());
                // refs to THIS reference site
                int m = 0;
                for (Reference r : getReferencesTo(toAddr(a))) {
                    out.println("     <- referenced by " + r.getFromAddress() + " " + r.getReferenceType());
                    if (++m > 6) { out.println("     ...(more)"); break; }
                }
                if (++n > 12) { out.println("  ...(more hits)"); break; }
                addr = addr.add(1);
            }
            out.println();
        }
        out.close();
    }
}
