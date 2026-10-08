import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import java.io.PrintWriter;

public class Action17MP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfmp_action17.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] funcs = {
            0x004CAA4AL, // THE apply-custom-action function (via Enter handler)
            0x004E78FAL, // Enter payload packer
            0x004DBD34L, // Exit payload packer
            0x004D92E9L, // Exit descriptor slot (payload? another packer)
            0x0099AEEDL, // enter sender helper (with the 3 values)
            0x0094E27FL  // enter sender helper 2
        };
        for (long f : funcs) {
            Function cf = getFunctionAt(toAddr(f));
            out.println("=== 0x" + Long.toHexString(f) + " (" + (cf != null ? cf.getName() : "no-fn") + ") ===");
            if (cf != null) {
                DecompileResults dr = ifc.decompileFunction(cf, 150, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 5500) { c = c.substring(0, 5500) + "\n...(truncated)"; }
                    out.println(c);
                }
            }
            out.println();
        }

        // byte pattern of FUN_004caa4a for the SP cross-search
        out.println("=== FUN_004caa4a first 96 bytes (for SP byte search) ===");
        byte[] bb = new byte[96];
        if (currentProgram.getMemory().getBytes(toAddr(0x004CAA4AL), bb) == 96) {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < 96; i++) {
                sb.append(String.format("%02X", bb[i]));
                if ((i + 1) % 16 == 0) { sb.append("\n"); } else { sb.append(" "); }
            }
            out.println(sb.toString());
        }
        out.close();
    }
}
