import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.address.Address;
import java.io.PrintWriter;

public class Action60SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action60.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        Function tmain = getFunctionAt(toAddr(0xF19859L));
        if (tmain == null) { tmain = createFunction(toAddr(0xF19859L), null); }
        out.println("=== ___tmainCRTStartup body CALL/JMP targets into game code ===");
        if (tmain != null && tmain.getBody() != null) {
            var insns = currentProgram.getListing().getInstructions(tmain.getBody(), true);
            int n = 0;
            while (insns.hasNext() && n < 20000) {
                Instruction ins = insns.next();
                n++;
                String m = ins.getMnemonicString();
                if (!m.equals("CALL") && !m.equals("JMP")) { continue; }
                Address t = null;
                for (int i = 0; i < ins.getNumOperands(); i++) {
                    Object[] objs = ins.getOpObjects(i);
                    for (Object o : objs) {
                        if (o instanceof Address) { t = (Address) o; }
                    }
                }
                if (t == null) { continue; }
                long v = t.getOffset();
                if (v >= 0x400000L && v < 0x2F00000L && (v < 0xF00000L || v > 0xF50000L)) {
                    Function cf = getFunctionAt(t);
                    out.println("  " + ins.getAddress() + ": " + ins.toString() + " -> " + t +
                                (cf != null ? " (" + cf.getName() + ")" : ""));
                    if (cf == null) {
                        Function nf = createFunction(t, null);
                        out.println("     created: " + (nf != null ? nf.getEntryPoint().toString() : "FAILED"));
                        if (nf != null) {
                            DecompileResults dr = ifc.decompileFunction(nf, 120, monitor);
                            if (dr.getDecompiledFunction() != null) {
                                String c = dr.getDecompiledFunction().getC();
                                if (c.length() > 4000) { c = c.substring(0, 4000) + "\n...(truncated)"; }
                                out.println(c);
                            }
                        }
                    }
                }
            }
            out.println("(scanned " + n + " instructions)");
        }
        out.close();
    }
}
