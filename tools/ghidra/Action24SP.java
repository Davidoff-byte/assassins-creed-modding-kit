import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action24SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action24.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        out.println("=== DAT_01e3d7b4 value (vtable of the +0x1D0 class) ===");
        long vt = getInt(toAddr(0x01E3D7B4L)) & 0xFFFFFFFFL;
        out.println("vtable = 0x" + Long.toHexString(vt));
        var s = getSymbolAt(toAddr(vt));
        if (s != null) { out.println("symbol: " + s.getName(true)); }

        out.println("=== +0x1D0 init value in the ctor (byte at hit+7) ===");
        out.println("init word = 0x" + Integer.toHexString(getByte(toAddr(0x01B975FDL + 7)) & 0xFF) +
                    Integer.toHexString(getByte(toAddr(0x01B975FDL + 6)) & 0xFF));

        out.println("=== refs to DAT_01e3d7b4 (who uses this vtable) ===");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(0x01E3D7B4L))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + " in " + cf);
            if (++n > 25) { out.println("  ...(more)"); break; }
        }

        out.println("=== refs to the vtable 0x" + Long.toHexString(vt) + " ===");
        n = 0;
        for (Reference r : getReferencesTo(toAddr(vt))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + " in " + cf);
            if (++n > 25) { out.println("  ...(more)"); break; }
        }
        out.println();

        // also: the MP ctor FUN_0186b210 wrote DAT_01e3d7b4 into the player controller - confirm
        Function cf2 = getFunctionAt(toAddr(0x0186B210L));
        out.println("=== reminder: player-controller ctor 0x186b210 uses DAT_01e3d7b4? ===");
        if (cf2 != null) {
            DecompileResults dr = ifc.decompileFunction(cf2, 90, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                out.println(c.length() > 2500 ? c.substring(0, 2500) + "\n...(truncated)" : c);
            }
        }
        out.close();
    }
}
