import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import java.io.File;
import java.io.PrintWriter;

// Usage: DumpAllDecomp.java <outDir> [chunkSize] [minAddr [maxAddr]]
// Writes decompiled C for every function to acc_NNNN.c files (chunkSize functions each).
public class DumpAllDecomp extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String outDir = args.length > 0 ? args[0] : "C:\\Users\\Administrator\\ghidra-acc\\acc-decomp";
        int chunkSize = args.length > 1 ? Integer.parseInt(args[1]) : 1500;
        long min = args.length > 2 ? Long.parseLong(args[2]) : 0L;
        long max = args.length > 3 ? Long.parseLong(args[3]) : 0x7fffffffffffL;
        new File(outDir).mkdirs();

        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        PrintWriter out = null;
        int inChunk = 0, chunkNo = 0, total = 0, ok = 0;
        FunctionIterator it = currentProgram.getFunctionManager().getFunctions(true);
        for (Function f : it) {
            long ea = f.getEntryPoint().getOffset();
            if (ea < min || ea > max) continue;
            if (out == null || inChunk >= chunkSize) {
                if (out != null) out.close();
                out = new PrintWriter(new File(outDir, String.format("acc_%05d.c", chunkNo++)), "UTF-8");
                inChunk = 0;
            }
            inChunk++; total++;
            out.println("// " + f.getEntryPoint() + " size=" + f.getBody().getNumAddresses() + " " + f.getName());
            DecompileResults res = ifc.decompileFunction(f, 45, monitor);
            if (res != null && res.decompileCompleted() && res.getDecompiledFunction() != null) {
                out.println(res.getDecompiledFunction().getC());
                ok++;
            } else {
                out.println("void " + f.getName() + "(void) { }");
            }
            if (total % 2000 == 0) println("DumpAllDecomp: " + total + " (" + ok + " ok)");
        }
        if (out != null) out.close();
        ifc.dispose();
        println("DumpAllDecomp: DONE total=" + total + " ok=" + ok);
    }
}
