// Decompile the functions at the given VAs: -postScript DumpFuncs.java <outdir> <va> <va> ...
import java.io.File;
import java.io.FileWriter;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.util.task.ConsoleTaskMonitor;

public class DumpFuncs extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        File out = new File(a.length > 0 ? a[0] : "funcs");
        out.mkdirs();
        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        ConsoleTaskMonitor mon = new ConsoleTaskMonitor();
        for (int i = 1; i < a.length; i++) {
            long va = Long.parseUnsignedLong(a[i].replace("0x", ""), 16);
            Address addr = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(va);
            Function f = getFunctionContaining(addr);
            if (f == null) { println("no function at " + a[i]); continue; }
            DecompileResults r = dec.decompileFunction(f, 120, mon);
            String name = f.getEntryPoint() + "_" + f.getName() + ".c";
            if (r != null && r.decompileCompleted() && r.getDecompiledFunction() != null) {
                FileWriter w = new FileWriter(new File(out, name));
                w.write("// " + a[i] + " -> " + f.getEntryPoint() + " " + f.getName() + "\n");
                w.write(r.getDecompiledFunction().getC());
                w.close();
                println("wrote " + name);
            } else {
                println("decompile failed " + a[i]);
            }
        }
    }
}
