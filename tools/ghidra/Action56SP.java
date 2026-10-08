import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

public class Action56SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action56.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] addrs = { 0xF199C6L, 0xF1DE71L, 0xD44BB0L, 0xD00750L, 0xD08970L,
                         0x5364A670L, 0x6803C99EL, 0x67280F60L, 0x5552075CL };
        for (long a : addrs) {
            Function cf = getFunctionContaining(toAddr(a));
            out.println("=== 0x" + Long.toHexString(a) + " in " + (cf != null ? cf.getEntryPoint() + " " + cf.getName() : "NO-FN") + " ===");
            if (cf != null) {
                DecompileResults dr = ifc.decompileFunction(cf, 60, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 2500) { c = c.substring(0, 2500) + "\n...(truncated)"; }
                    out.println(c);
                }
            }
            out.println();
        }
        out.close();
    }
}
