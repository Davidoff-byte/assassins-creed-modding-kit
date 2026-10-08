import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action47SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action47.txt", "UTF-8");
        Memory mem = currentProgram.getMemory();
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] funcs = { 0x00503600L, 0x0073C2C0L, 0x0073C090L };
        for (long f : funcs) {
            Function cf = getFunctionAt(toAddr(f));
            out.println("=== 0x" + Long.toHexString(f) + " (" + (cf != null ? cf.getName() : "no-fn") + ") ===");
            if (cf != null) {
                DecompileResults dr = ifc.decompileFunction(cf, 150, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 4500) { c = c.substring(0, 4500) + "\n...(truncated)"; }
                    out.println(c);
                }
                out.println("--- refs to " + cf.getEntryPoint() + " ---");
                int n = 0;
                for (Reference r : getReferencesTo(cf.getEntryPoint())) {
                    Function c2 = getFunctionContaining(r.getFromAddress());
                    out.println("  " + r.getFromAddress() + " in " + c2);
                    if (++n > 15) { out.println("  ...(more)"); break; }
                }
            }
            out.println();
        }

        // widen: who stores pointers into 0x01E68800..0x01E68A80 (vtable base candidates)
        out.println("=== vtable-base pointer store search (0x1e68800..0x1e68a80, step 0x10) ===");
        for (long b = 0x01E68800L; b <= 0x01E68A80L; b += 0x10) {
            byte[] bb = {(byte)(b & 0xFF), (byte)((b >> 8) & 0xFF), (byte)((b >> 16) & 0xFF), (byte)((b >> 24) & 0xFF)};
            Address addr = toAddr(0x400000L);
            int n = 0;
            while (true) {
                addr = mem.findBytes(addr, bb, null, true, monitor);
                if (addr == null) break;
                Function f = getFunctionContaining(addr);
                var sym = getSymbolAt(addr);
                out.println("  vtable 0x" + Long.toHexString(b) + " stored @" + addr + (f != null ? " in " + f.getName() : sym != null ? " (sym " + sym.getName(true) + ")" : ""));
                if (++n > 4) { out.println("  ..."); break; }
                addr = addr.add(1);
            }
        }
        out.close();
    }
}
