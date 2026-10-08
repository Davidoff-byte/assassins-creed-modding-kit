import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action46SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action46.txt", "UTF-8");
        Memory mem = currentProgram.getMemory();

        // dump the vtable region around the FUN_0073c190 slot (0x01E68AF4)
        out.println("=== vtable region 0x01e68a80..0x01e68b20 ===");
        for (long a = 0x01E68A80L; a <= 0x01E68B20L; a += 4) {
            try {
                long v = getInt(toAddr(a)) & 0xFFFFFFFFL;
                String nm = "";
                Function f = getFunctionAt(toAddr(v));
                if (f != null) { nm = " " + f.getName(); }
                out.println(String.format("  %08X: %08X%s", a, v, nm));
            } catch (Exception e) { }
        }
        out.println();

        // who stores pointers into that vtable region (the descriptor / ctors)
        long[] bases = {0x01E68A80L, 0x01E68A90L, 0x01E68AA0L, 0x01E68AB0L, 0x01E68AC0L, 0x01E68AD0L, 0x01E68AE0L, 0x01E68AF0L};
        for (long b : bases) {
            byte[] bb = new byte[4];
            bb[0] = (byte)(b & 0xFF); bb[1] = (byte)((b >> 8) & 0xFF); bb[2] = (byte)((b >> 16) & 0xFF); bb[3] = (byte)((b >> 24) & 0xFF);
            Address addr = toAddr(0x400000L);
            int n = 0;
            while (true) {
                addr = mem.findBytes(addr, bb, null, true, monitor);
                if (addr == null) break;
                long a = addr.getOffset();
                Function f = getFunctionContaining(toAddr(a));
                var sym = getSymbolAt(toAddr(a));
                out.println("ptr to 0x" + Long.toHexString(b) + " stored @" + addr + (f != null ? " in " + f.getName() : sym != null ? " (sym " + sym.getName(true) + ")" : ""));
                for (Reference r : getReferencesTo(toAddr(a))) {
                    out.println("     <- ref by " + r.getFromAddress() + " in " + getFunctionContaining(r.getFromAddress()));
                }
                if (++n > 6) { out.println("  ...(more)"); break; }
                addr = addr.add(1);
            }
        }
        out.close();
    }
}
