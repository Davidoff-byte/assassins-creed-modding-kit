import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.Symbol;
import java.io.PrintWriter;

public class Chain14 extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_chain14.txt", "UTF-8");
        Memory mem = currentProgram.getMemory();

        long[] callerTargets = { 0x1128f70L, 0x12398a0L };
        for (long t : callerTargets) {
            out.println("=== callers of 0x" + Long.toHexString(t) + " ===");
            for (Reference r : getReferencesTo(toAddr(t))) {
                out.println("  from " + r.getFromAddress() + "  " + r.getReferenceType());
                Function cf = getFunctionContaining(r.getFromAddress());
                if (cf != null) out.println("      in " + cf.getEntryPoint() + " " + cf.getName());
            }
            out.println();
        }

        long[] fns = { 0x741ab0L, 0x52b180L, 0x5ba020L };
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        for (long p : fns) {
            Address ad = toAddr(p);
            Function f = getFunctionContaining(ad);
            if (f == null) { try { disassemble(ad); } catch (Exception e) {} f = createFunction(ad, null); }
            out.println("=== fn 0x" + Long.toHexString(p) + "  " + (f != null ? (f.getEntryPoint()+" "+f.getName()) : "NOFUNC") + " ===");
            if (f != null) {
                DecompileResults r = ifc.decompileFunction(f, 180, monitor);
                if (r.getDecompiledFunction() != null) out.println(r.getDecompiledFunction().getC());
                else out.println("(decompile failed)");
            }
            out.println();
        }

        out.println("=== vtable dump at 0x02697010 (src+0) ===");
        Address vt = toAddr(0x02697010L);
        for (int off = 0; off <= 0x120; off += 4) {
            Address p = vt.add(off);
            int val = mem.getInt(p);
            if (val == 0) continue;
            String note = "";
            long va = val & 0xFFFFFFFFL;
            if (va >= 0x400000 && va < 0x2B00000) {
                Symbol fs = getSymbolAt(toAddr(va));
                note = "  -> " + (fs != null ? fs.getName(true) : "EXE +0x" + Long.toHexString(va - 0x400000));
            }
            String sym = "";
            Symbol ss = getSymbolAt(p);
            if (ss != null) sym = "   [" + ss.getName(true) + "]";
            out.println("  +0x" + Integer.toHexString(off) + ": 0x" + String.format("%08X", val) + note + sym);
        }
        out.close();
    }
}
