import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import java.io.PrintWriter;

public class Action41SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action41.txt", "UTF-8");
        Memory mem = currentProgram.getMemory();
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[][] pats = {
            {0x3F742D26L, 0x26, 0x2D, 0x74, 0x3F}, // shared base hash
            {0x2F4222CAL, 0xCA, 0x22, 0x42, 0x2F}, // class 0x01E64680 hash
            {0x0984415EL, 0x5E, 0x41, 0x84, 0x09}, // class 0x01E4A128 hash
        };
        for (long[] p : pats) {
            byte[] bb = {(byte) p[1], (byte) p[2], (byte) p[3], (byte) p[4]};
            out.println("=== hash 0x" + Long.toHexString(p[0]) + " occurrences ===");
            Address addr = toAddr(0x400000L);
            int n = 0;
            while (true) {
                addr = mem.findBytes(addr, bb, null, true, monitor);
                if (addr == null) break;
                long a = addr.getOffset();
                Function cf = getFunctionContaining(toAddr(a));
                out.println("  @" + addr + " in " + cf);
                if (cf != null && n < 3) {
                    DecompileResults dr = ifc.decompileFunction(cf, 120, monitor);
                    out.println("--- fn " + cf.getEntryPoint() + " ---");
                    if (dr.getDecompiledFunction() != null) {
                        String c = dr.getDecompiledFunction().getC();
                        if (c.length() > 3500) { c = c.substring(0, 3500) + "\n...(truncated)"; }
                        out.println(c);
                    }
                }
                if (++n > 12) { out.println("  ...(more)"); break; }
                addr = addr.add(1);
            }
            out.println();
        }
        out.close();
    }
}
