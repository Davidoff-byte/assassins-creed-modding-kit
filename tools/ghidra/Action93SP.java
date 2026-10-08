import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Action93SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action93.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        long[] strAddrs = { 0x01E5CA70L, 0x01E428F8L, 0x01E48DC4L, 0x01E5E664L,
                            0x01E54E90L, 0x01E4EEBCL, 0x01E5E650L, 0x01E4A6C8L };
        String[] names = { "Ai::SpawningManagerUpdate", "SpawnEntityParams", "SpawningSpecification",
                           "Spawner", "AbstractSceneSpawner", "AbstractSceneSpawningComponent",
                           "SpawnerActionEvent", "PlayerSpawnEvent" };
        for (int i = 0; i < strAddrs.length; i++) {
            out.println("=== refs to \"" + names[i] + "\" (0x" + Long.toHexString(strAddrs[i]) + ") ===");
            for (Reference r : getReferencesTo(toAddr(strAddrs[i]))) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("  from " + r.getFromAddress() + (cf != null ? " in " + cf.getName() + " @" + cf.getEntryPoint() : ""));
            }
            out.println();
        }

        // decompile the function containing the SpawningManagerUpdate marker
        out.println("=== the SpawningManagerUpdate function ===");
        for (Reference r : getReferencesTo(toAddr(0x01E5CA70L))) {
            Function cf = getFunctionContaining(r.getFromAddress());
            if (cf != null) {
                out.println("--- " + cf.getName() + " @" + cf.getEntryPoint() + " size=" + cf.getBody().getNumAddresses() + " ---");
                DecompileResults dr = ifc.decompileFunction(cf, 200, monitor);
                if (dr.getDecompiledFunction() != null) {
                    String c = dr.getDecompiledFunction().getC();
                    if (c.length() > 12000) { c = c.substring(0, 12000) + "\n...(truncated)"; }
                    out.println(c);
                }
                break;
            }
        }
        out.close();
    }
}
