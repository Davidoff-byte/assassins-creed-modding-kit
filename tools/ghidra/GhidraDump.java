// Decompile every function in the current program to <outdir>/<entrypoint>_<name>.c for gamedb.
// Run headless:
//   analyzeHeadless <projdir> <proj> -import <dll> -postScript GhidraDump.java <outdir> -scriptPath <this dir>
// or on an already-analysed program:
//   analyzeHeadless <projdir> <proj> -process <dllname> -noanalysis -postScript GhidraDump.java <outdir> -scriptPath <this dir>

import java.io.File;
import java.io.FileWriter;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.util.task.ConsoleTaskMonitor;

public class GhidraDump extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        File outdir = new File(args.length > 0 ? args[0] : "decomp");
        outdir.mkdirs();

        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        ConsoleTaskMonitor mon = new ConsoleTaskMonitor();

        FunctionIterator it = currentProgram.getFunctionManager().getFunctions(true);
        int n = 0;
        while (it.hasNext()) {
            Function f = it.next();
            try {
                DecompileResults res = dec.decompileFunction(f, 60, mon);
                if (res != null && res.decompileCompleted() && res.getDecompiledFunction() != null) {
                    String c = res.getDecompiledFunction().getC();
                    String name = f.getEntryPoint().toString() + "_" + f.getName() + ".c";
                    FileWriter w = new FileWriter(new File(outdir, name));
                    w.write(c);
                    w.close();
                    n++;
                }
            } catch (Exception e) {
                // skip functions the decompiler chokes on
            }
        }
        println("GhidraDump: wrote " + n + " functions to " + outdir.getAbsolutePath());
    }
}
