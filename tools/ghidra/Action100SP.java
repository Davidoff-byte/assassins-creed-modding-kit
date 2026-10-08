import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action100SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action100.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        // what sits at 0x1e5c950 (the AI phase table entry referencing the registrar)?
        out.println("=== data at 0x01e5c900 .. 0x01e5c9a0 ===");
        for (long p = 0x01E5C900L; p < 0x01E5C9A0L; p += 4) {
            int v = getInt(toAddr(p));
            Function cf = getFunctionContaining(toAddr(v & 0xFFFFFFFFL));
            String extra = (cf != null) ? cf.getName() : "";
            // is it a string pointer?
            if ((v & 0xFFFFFFFFL) > 0x1E00000L && (v & 0xFFFFFFFFL) < 0x2B00000L) {
                try {
                    StringBuilder sb = new StringBuilder();
                    for (int i = 0; i < 48; i++) {
                        byte b = getByte(toAddr((v & 0xFFFFFFFFL) + i));
                        if (b == 0) { break; }
                        if (b < 32 || b > 126) { sb.setLength(0); break; }
                        sb.append((char) b);
                    }
                    if (sb.length() > 2) { extra = "\"" + sb + "\""; }
                } catch (Exception e) {
                }
            }
            out.println(String.format("  0x%08X: 0x%08X %s", p, v, extra));
        }
        out.println();

        // who references the table start (the AI init)?
        for (long t : new long[]{0x01E5C950L, 0x01E5C948L, 0x01E5C900L}) {
            out.println("=== refs to 0x" + Long.toHexString(t) + " ===");
            for (Reference r : getReferencesTo(toAddr(t))) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("  from " + r.getFromAddress() + (cf != null ? " in " + cf.getName() + " @" + cf.getEntryPoint() : ""));
            }
        }
        out.close();
    }
}
