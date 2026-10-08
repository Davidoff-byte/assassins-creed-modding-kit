// DecompilePawn.java - decompile the ADishonoredPlayerPawn power methods and
// one level of callees, to trace power activation down to the component.
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;
import java.util.LinkedHashSet;

public class DecompilePawn extends GhidraScript {

    private static final long[] ROOTS = {
        0x00f74680L, // OnAddPower
        0x00f746a0L, // OnRemovePower
        0x00f74700L, // OnMaxPowers
        0x00f74720L, // OnMinPowers
        0x00f74800L, // OnTogglePowerWheel
        0x00f74960L, // OnCancelPlayerActivePower
    };

    @Override
    public void run() throws Exception {
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter(
            "C:\\Users\\Administrator\\ghidra_scripts\\pawn_decomp_out.txt", "UTF-8");

        LinkedHashSet<Function> seen = new LinkedHashSet<>();

        // gather roots + one level of callees
        LinkedHashSet<Function> todo = new LinkedHashSet<>();
        for (long a : ROOTS) {
            Function f = getFunctionAt(toAddr(a));
            if (f != null) todo.add(f);
        }
        while (!todo.isEmpty()) {
            Function f = todo.iterator().next();
            todo.remove(f);
            if (!seen.add(f)) continue;
            // collect callees
            for (Address addr = f.getBody().getMinAddress(); addr != null
                    && addr.compareTo(f.getBody().getMaxAddress()) <= 0;) {
                Instruction ins = getInstructionAt(addr);
                if (ins == null) break;
                for (Reference r : ins.getReferencesFrom()) {
                    if (r.getReferenceType().isCall()) {
                        Function callee = getFunctionAt(r.getToAddress());
                        if (callee != null && !seen.contains(callee)) todo.add(callee);
                    }
                }
                addr = addr.add(ins.getLength());
            }
        }

        for (Function f : seen) {
            out.println("==================================================");
            out.println("FUNCTION " + f.getEntryPoint() + " name=" + f.getName());
            DecompileResults res = ifc.decompileFunction(f, 120, monitor);
            if (res != null && res.decompileCompleted() && res.getDecompiledFunction() != null) {
                out.println(res.getDecompiledFunction().getC());
            } else {
                out.println("  decompile failed");
            }
            out.println();
        }

        out.close();
        ifc.dispose();
        println("DecompilePawn done: " + seen.size() + " functions");
    }
}
