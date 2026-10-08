import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

// AccCoop A4: find code that references the spawn-related type-name strings.
public class RefsToAddr extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] targets = {
            0x1429cb930L, // SpawnCharacterParams
            0x142368950L, // AbstractSceneSpawner
            0x142368930L, // AbstractSceneSpawningComponent
            0x142374378L, // SpawnOperator
            0x142374340L, // SpawnOperatorData
            0x1423689e8L, // EntitySpawnedActor
            0x14236f680L, // SpawnPositionComponent
            0x142373fa8L, // PlayerSpawnActivatorComponent
            0x1429d21c8L, // SpawnEntityOperator
            0x1429d21b0L, // SpawnEntityOperatorData
        };
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\refs_spawn.txt", "UTF-8");
        for (long t : targets) {
            Address a = toAddr(t);
            out.println("=== refs to " + a);
            int n = 0;
            for (Reference r : getReferencesTo(a)) {
                Function f = getFunctionContaining(r.getFromAddress());
                out.println("   " + r.getFromAddress() + "  " +
                            (f != null ? (f.getEntryPoint() + " " + f.getName()) : "code"));
                n++;
            }
            out.println("   (" + n + " refs)");
        }
        out.close();
    }
}
