import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.address.Address;
import java.io.PrintWriter;

public class Action105SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action105.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        // find the function starts containing 0x602CE0 and 0x6060F3 by scanning backward
        // for a prologue
        long[] sites = { 0x602CE0L, 0x6060F3L, 0x602B34L };
        for (long site : sites) {
            out.println("=== site 0x" + Long.toHexString(site) + " ===");
            long start = 0;
            for (long a = site; a > site - 0x600; a--) {
                Instruction ins = getInstructionAt(toAddr(a));
                if (ins == null) { continue; }
                // common prologues
                String s = ins.toString();
                if (s.equals("PUSH EBP") && a + 3 < site) {
                    Instruction next = getInstructionAt(toAddr(a + 1));
                    if (next != null && next.toString().startsWith("MOV EBP,ESP")) {
                        start = a;
                        break;
                    }
                }
                if (s.equals("PUSH EBP")) { start = a; break; }
            }
            out.println("  candidate function start: 0x" + Long.toHexString(start));
            Function fn = getFunctionContaining(toAddr(site));
            if (fn == null && start != 0) {
                fn = createFunction(toAddr(start), null);
                out.println("  created function: " + (fn != null ? fn.getEntryPoint().toString() : "FAILED"));
            } else if (fn != null) {
                out.println("  existing function: " + fn.getName() + " @" + fn.getEntryPoint());
            }
            if (fn != null) {
                DecompileResults dr = ifc.decompileFunction(fn, 200, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 12000) { c = c.substring(0, 12000) + "\n...(truncated)"; }
                    out.println(c);
                }
            }
            out.println();
        }
        out.close();
    }
}
