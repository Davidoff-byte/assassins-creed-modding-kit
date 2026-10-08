import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

// Refs to a hardcoded set of BF SP data addresses (spawn/player anchors + camera position).
public class RefsToManyBFSP extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] targets = {
            0x01e4a6c8L, // PlayerSpawnEvent
            0x026faeb0L, // SpawnPlayerParams
            0x01e54ed0L, // PlayerSpawnActivatorComponent
            0x01e525e8L, // EntitySpawnedActor
            0x01e54e90L, // AbstractSceneSpawner
            0x02abe530L, // camera position global (vec4)
            0x01e4eebcL, // AbstractSceneSpawningComponent
            0x01e428f8L  // SpawnEntityParams
        };
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_spawn_refs.txt", "UTF-8");
        for (long t : targets) {
            Address ad = toAddr(t);
            out.println("=== 0x" + Long.toHexString(t) + " ===");
            int n = 0;
            for (Reference r : getReferencesTo(ad)) {
                Address from = r.getFromAddress();
                Function f = getFunctionContaining(from);
                String who = (f != null) ? (f.getEntryPoint() + " " + f.getName()) : ("code " + from);
                out.println("  " + who + "\t" + from + "\t" + r.getReferenceType());
                n++;
            }
            out.println("  TOTAL " + n);
        }
        out.close();
    }
}
