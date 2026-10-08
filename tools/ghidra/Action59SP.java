import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolTable;
import java.io.PrintWriter;

public class Action59SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action59.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        // 1) raw listing of the CRT entry
        out.println("=== CRT entry 0xf199c6 listing ===");
        for (long a = 0xF199C6L; a <= 0xF199E0L; ) {
            Instruction ins = getInstructionAt(toAddr(a));
            if (ins == null) { out.println(String.format("  %08X: (no insn)", a)); break; }
            out.println("  " + ins.getAddress() + ": " + ins.toString());
            a = ins.getAddress().getOffset() + ins.getLength();
        }
        out.println();

        // 2) find ___tmainCRTStartup symbol + decompile it to find main()
        Function tmain = null;
        SymbolTable st = currentProgram.getSymbolTable();
        for (Symbol s : st.getAllSymbols(true)) {
            if (s.getName().contains("tmainCRTStartup")) {
                tmain = getFunctionAt(s.getAddress());
                out.println("=== " + s.getName(true) + " @" + s.getAddress() + " ===");
            }
        }
        if (tmain == null) {
            out.println("tmainCRTStartup symbol not found");
        } else {
            // call references FROM tmain (main() = one of them)
            out.println("=== calls from ___tmainCRTStartup ===");
            int shown = 0;
            for (Reference r : getReferencesFrom(tmain.getEntryPoint())) {
                if (!r.getReferenceType().isCall()) { continue; }
                Function cf = getFunctionAt(r.getToAddress());
                out.println("  -> " + r.getToAddress() + (cf != null ? " " + cf.getName() : ""));
                if (cf == null && shown < 3) {
                    shown++;
                    Function nf = createFunction(r.getToAddress(), null);
                    out.println("     created fn " + (nf != null ? nf.getEntryPoint().toString() : "FAILED"));
                    if (nf != null) {
                        DecompileResults dr = ifc.decompileFunction(nf, 120, monitor);
                        if (dr.getDecompiledFunction() != null) {
                            String c = dr.getDecompiledFunction().getC();
                            if (c.length() > 5000) { c = c.substring(0, 5000) + "\n...(truncated)"; }
                            out.println(c);
                        }
                    }
                }
            }
        }
        out.close();
    }
}
