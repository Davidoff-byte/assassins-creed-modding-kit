import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action33SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action33.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        // A) callers of the behavior-name registry lookup
        out.println("=== refs to FUN_00a1c970 (behavior-name lookup) ===");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(0x00A1C970L))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("  " + r.getFromAddress() + " in " + cf);
            if (++n > 60) { out.println("  ...(more)"); break; }
        }
        out.println();

        // B) neighborhood of the BhvGenericNPC reflection string: look for fn pointers
        out.println("=== data around 0x26e2820 (BhvGenericNPC reflection entry) ===");
        for (int i = -32; i < 16; i++) {
            long a = 0x026E2820L + i * 4L;
            try {
                long v = getInt(toAddr(a)) & 0xFFFFFFFFL;
                String extra = "";
                if (v >= 0x400000L && v < 0x3000000L) {
                    Function f = getFunctionAt(toAddr(v));
                    var s = getSymbolAt(toAddr(v));
                    if (f != null) { extra = "  <- FUN " + f.getName(); }
                    else if (s != null) { extra = "  sym " + s.getName(true); }
                    else {
                        // maybe a string: read 16 bytes
                        byte[] sb = new byte[16];
                        currentProgram.getMemory().getBytes(toAddr(v), sb);
                        StringBuilder st = new StringBuilder();
                        for (byte b : sb) { if (b >= 32 && b < 127) { st.append((char) b); } else { break; } }
                        if (st.length() >= 3) { extra = "  str \"" + st + "\""; }
                    }
                }
                out.println(String.format("  +0x%03X 0x%08X%s", (i + 32) * 4, v, extra));
            } catch (Exception e) { }
        }
        out.close();
    }
}
