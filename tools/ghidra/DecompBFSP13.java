import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

public class DecompBFSP13 extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] probes = { 0x0112217AL, 0x0040FF3CL };
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_writer_chain.txt", "UTF-8");
        for (long p : probes) {
            Address ad = toAddr(p);
            Function f = getFunctionContaining(ad);
            if (f == null) {
                try { disassemble(ad); } catch (Exception e) {}
                f = createFunction(ad, null);
            }
            out.println("=== probe 0x" + Long.toHexString(p) + "  function: " +
                        (f != null ? (f.getEntryPoint() + " " + f.getName()) : "NOFUNC") + " ===");
            if (f != null) {
                DecompileResults r = ifc.decompileFunction(f, 180, monitor);
                if (r.getDecompiledFunction() != null) out.println(r.getDecompiledFunction().getC());
                else out.println("(decompile failed)");
            }
            out.println();
        }
        out.close();
    }
}
