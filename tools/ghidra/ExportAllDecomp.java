import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.FunctionManager;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;

/**
 * Mass-decompiles every function of the current program into resumable, gamedb-indexable
 * C batch files. Args:
 *   [0] output dir            (default C:\Users\Administrator\bf4_re\sp_src)
 *   [1] functions per file    (default 500)
 *   [2] state prefix          (default sp)
 * Resume: re-run; it continues from the state file. Files are written at batch boundaries.
 */
public class ExportAllDecomp extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String outDir = args.length > 0 ? args[0] : "C:\\Users\\Administrator\\bf4_re\\sp_src";
        int batch = args.length > 1 ? Integer.parseInt(args[1]) : 500;
        String prefix = args.length > 2 ? args[2] : "sp";

        new File(outDir).mkdirs();
        String statePath = outDir + File.separator + "state_" + prefix + ".txt";
        int startIndex = 0;
        File stateFile = new File(statePath);
        if (stateFile.exists()) {
            try (BufferedReader br = new BufferedReader(new FileReader(stateFile))) {
                String line = br.readLine();
                if (line != null && !line.trim().isEmpty()) {
                    startIndex = Integer.parseInt(line.trim());
                }
            } catch (Exception ignored) {
            }
        }

        DecompInterface ifc = new DecompInterface();
        ifc.setOptions(new DecompileOptions());
        if (!ifc.openProgram(currentProgram)) {
            println("ERROR: decompiler could not open program");
            return;
        }

        FunctionManager fm = currentProgram.getFunctionManager();
        FunctionIterator it = fm.getFunctions(true);

        int index = 0;
        int writtenInFile = 0;
        int fileNo = startIndex / batch;
        BufferedWriter w = null;
        long t0 = System.currentTimeMillis();

        while (it.hasNext()) {
            Function f = it.next();
            if (index < startIndex) {
                index++;
                continue;
            }
            if (w == null) {
                String fn = String.format("%s%spart_%05d.c", outDir, File.separator, fileNo);
                w = new BufferedWriter(new FileWriter(fn, false), 1 << 20);
                writtenInFile = 0;
            }
            w.write("// ==== " + f.getName() + " @ " + f.getEntryPoint() + " ====\n");
            String c = null;
            try {
                DecompileResults dr = ifc.decompileFunction(f, 30, monitor);
                if (dr != null && dr.getDecompiledFunction() != null) {
                    c = dr.getDecompiledFunction().getC();
                }
            } catch (Throwable t) {
                c = null;
            }
            if (c == null) {
                c = "void " + f.getName() + "(void) { /* decompile failed */ }\n";
            }
            w.write(c);
            w.write("\n");
            writtenInFile++;
            index++;
            if (writtenInFile >= batch) {
                w.close();
                w = null;
                fileNo++;
                try (BufferedWriter sw = new BufferedWriter(new FileWriter(statePath, false))) {
                    sw.write(Integer.toString(index));
                }
                long secs = (System.currentTimeMillis() - t0) / 1000;
                println("progress: " + index + " functions (" + fileNo + " files, " + secs + "s)");
                monitor.checkCancelled();
            }
        }
        if (w != null) {
            w.close();
        }
        try (BufferedWriter sw = new BufferedWriter(new FileWriter(statePath, false))) {
            sw.write(Integer.toString(index));
        }
        ifc.dispose();
        println("DONE: " + index + " functions exported to " + outDir);
    }
}
