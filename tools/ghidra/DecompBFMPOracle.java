import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

// Decompile the Black Flag MP networked-avatar / replication functions (the co-op oracle).
public class DecompBFMPOracle extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] addrs = {
            0x004fd528L, // NetPlayer registration / factory
            0x004fa9adL, // NetPlayer-related
            0x00699771L, // NetPlayerActionHistoryManager
            0x004bf90eL, // S2C_SetMoveReplicationMode setup (movement replication)
            0x004bfcd3L, // S2C_SetMoveReplicationMode HANDLER (applies replicated move fields)
            0x00c2fdfcL, // replicated-field registration helper (offA/offB/offC)
            0x00c23e4eL, // object factory
            0x004d9140L, // enter custom action handler (parkour)
            0x004d92e9L, // exit custom action handler (parkour)
            0x0136f74cL, // S2C_SetMoveReplicationMode handler table
            0x004ce584L, // message registry (M2R_ReplicateEnterCustomActionState)
            0x0137272dL, // enter-custom-action handler
            0x00d78f28L, // avatarID
            0x00763857L, // avatarID
            0x0085e5feL  // avatarID
        };
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfmp_oracle_decomp.txt", "UTF-8");
        for (long a : addrs) {
            Address ad = toAddr(a);
            Function f = getFunctionAt(ad);
            if (f == null) {
                f = getFunctionContaining(ad);
            }
            out.println("=== " + Long.toHexString(a) + (f != null ? " " + f.getName() : " NOFUNC") + " ===");
            if (f != null) {
                DecompileResults r = ifc.decompileFunction(f, 60, monitor);
                if (r.getDecompiledFunction() != null) {
                    out.println(r.getDecompiledFunction().getC());
                } else {
                    out.println("(decompile failed)");
                }
            }
            out.println();
        }
        out.close();
    }
}
