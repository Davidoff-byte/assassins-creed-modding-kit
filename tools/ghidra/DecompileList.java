import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import java.io.BufferedReader;
import java.io.FileReader;
import java.io.PrintWriter;

public class DecompileList extends GhidraScript {
    @Override
    public void run() throws Exception {
        String listFile = "C:\\Users\\Administrator\\ghidra_scripts\\targets.txt";
        String outFile  = "C:\\Users\\Administrator\\ghidra_scripts\\decomp_set.txt";
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter(outFile, "UTF-8");
        BufferedReader br = new BufferedReader(new FileReader(listFile));
        String line;
        while ((line = br.readLine()) != null) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) {
                continue;
            }
            long t;
            try {
                t = Long.parseLong(line.replace("0x", "").replace("0X", ""), 16);
            } catch (Exception e) {
                out.println("=== BAD TARGET " + line);
                continue;
            }
            Address a = toAddr(t);
            Function f = getFunctionAt(a);
            out.println("==================================================");
            out.println("FUNCTION " + a + " name=" + (f != null ? f.getName() : "?"));
            if (f == null) {
                out.println("  (no function)");
                continue;
            }
            DecompileResults res = ifc.decompileFunction(f, 180, monitor);
            if (res != null && res.decompileCompleted() && res.getDecompiledFunction() != null) {
                out.println(res.getDecompiledFunction().getC());
            } else {
                out.println("  decompile failed: " + (res != null ? res.getErrorMessage() : "null"));
            }
        }
        br.close();
        out.close();
        ifc.dispose();
    }
}
