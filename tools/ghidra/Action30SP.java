import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action30SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action30.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long hit = 0x01AB537CL;
        Function wf = getFunctionContaining(toAddr(hit));
        out.println("=== writer fn (contains 0x1ab537c): " + (wf != null ? wf.getEntryPoint() + " " + wf.getName() : "NONE") + " ===");
        if (wf != null) {
            DecompileResults dr = ifc.decompileFunction(wf, 150, monitor);
            if (dr.getDecompiledFunction() != null) {
                String c = dr.getDecompiledFunction().getC();
                if (c.length() > 6000) { c = c.substring(0, 6000) + "\n...(truncated)"; }
                out.println(c);
            }
            // raw listing around the hit instruction
            out.println("--- disasm around 0x1ab537c ---");
            for (long a = 0x01AB5360L; a <= 0x01AB5390L; a += 1) {
                Instruction ins = getInstructionAt(toAddr(a));
                if (ins != null) {
                    out.println("  0x" + Long.toHexString(a) + ": " + ins.toString());
                    a = ins.getAddress().getOffset() + ins.getLength() - 1;
                }
            }
            out.println();
            out.println("=== refs to writer " + wf.getEntryPoint() + " ===");
            int n = 0;
            for (Reference r : getReferencesTo(wf.getEntryPoint())) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + " in " + cf);
                if (++n > 20) { out.println("  ...(more)"); break; }
            }
        }
        out.println();

        // nearby functions (the family) between 0x1ab5000 and 0x1ab5800
        out.println("=== function family 0x1ab5000..0x1ab5800 ===");
        var it = currentProgram.getFunctionManager().getFunctions(true);
        for (Function f : it) {
            long e = f.getEntryPoint().getOffset();
            if (e >= 0x01AB5000L && e <= 0x01AB5800L) {
                out.println("  fn " + f.getEntryPoint() + " " + f.getName());
            }
        }
        out.close();
    }
}
