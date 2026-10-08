import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action39SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action39.txt", "UTF-8");
        Memory mem = currentProgram.getMemory();

        long[][] pats = {
            {0x006DEFA0L, 0xA0, 0xEF, 0x6D, 0x00}, // ctor FUN_006defa0 (class 0x01E64680)
            {0x00504880L, 0x80, 0x48, 0x50, 0x00}, // ctor wrapper FUN_00504880
            {0x00503330L, 0x30, 0x33, 0x50, 0x00}, // ctor FUN_00503330 (class 0x01E4A128)
            {0x0052A4A0L, 0xA0, 0xA4, 0x52, 0x00}, // base node ctor FUN_0052a4a0
            {0x0073C190L, 0x90, 0xC1, 0x73, 0x00}, // create-node vtable method
            {0x01E64680L, 0x80, 0x46, 0xE6, 0x01}, // derived vtable
            {0x01E4A128L, 0x28, 0xA1, 0xE4, 0x01}, // mid vtable
        };
        for (long[] p : pats) {
            long val = p[0];
            byte[] bb = {(byte) p[1], (byte) p[2], (byte) p[3], (byte) p[4]};
            out.println("=== dword 0x" + Long.toHexString(val) + " occurrences ===");
            Address addr = toAddr(0x400000L);
            int n = 0;
            while (true) {
                addr = mem.findBytes(addr, bb, null, true, monitor);
                if (addr == null) break;
                long a = addr.getOffset();
                // context: dwords from a-0x30 to a+0xC
                StringBuilder ctx = new StringBuilder();
                for (int i = -12; i <= 3; i++) {
                    try {
                        ctx.append(String.format(" %08X", getInt(toAddr(a + i * 4L)) & 0xFFFFFFFFL));
                    } catch (Exception e) {
                        ctx.append(" ????????");
                    }
                }
                Function f = getFunctionAt(toAddr(a));
                var sym = getSymbolAt(toAddr(a));
                out.println("  @" + addr + (f != null ? " (fn " + f.getName() + ")" : sym != null ? " (sym " + sym.getName(true) + ")" : "") + ":" + ctx.toString());
                // refs TO this address
                int m = 0;
                for (Reference r : getReferencesTo(toAddr(a))) {
                    out.println("     <- referenced by " + r.getFromAddress() + " " + r.getReferenceType());
                    if (++m > 6) { out.println("     ...(more refs)"); break; }
                }
                if (++n > 10) { out.println("  ...(more hits)"); break; }
                addr = addr.add(1);
            }
            out.println();
        }
        out.close();
    }
}
