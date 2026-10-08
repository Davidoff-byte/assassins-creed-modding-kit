// PtrRE.java - walk references from a seed list (FName globals + Blink strings),
// following data pointers, and decompile every function that touches them.
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import java.io.PrintWriter;
import java.util.ArrayDeque;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Set;

public class PtrRE extends GhidraScript {

    private static final long[] SEEDS = {
        // cached FName globals from the tweak-name registry (name -> global)
        0x0145e3f8L, // Blink
        0x0145e400L, // BlinkCooldownTime
        0x0145e408L, // BlinkDistancePercentage
        0x0145e410L, // BlinkDistanceTravelled
        0x0145e418L, // Blink_opacity
        0x0145e420L, // BlinkLensIntensity
        0x0145e428L, // BlinkLocalDirection
        0x0145e430L, // BlinkStepProgress
        0x0145e438L, // BlinkStepsTaken
        0x0145e440L, // BlinkTargeting
        0x0145e448L, // BlinkTimeElapsed
        0x0145e450L, // BlinkWarmupTime
        // string data that had references
        0x010a5830L, 0x010a5840L,             // BlinkBlender, Blink
        0x01117240L, 0x0111733cL, 0x01117358L, 0x01117374L, 0x0111738cL, // PpBridge
        0x0111cc1cL,                          // Mantle Blink
    };

    private static final long[] EXTRA = {
        // also seed the +4 half of each 8-byte FName global
        0x0145e3fcL, 0x0145e404L, 0x0145e40cL, 0x0145e414L, 0x0145e41cL,
        0x0145e424L, 0x0145e42cL, 0x0145e434L, 0x0145e43cL, 0x0145e444L,
        0x0145e44cL, 0x0145e454L,
    };

    private final Set<Address> visited = new HashSet<>();
    private final LinkedHashMap<Address, Function> funcs = new LinkedHashMap<>();

    @Override
    public void run() throws Exception {
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        ArrayDeque<Address> queue = new ArrayDeque<>();
        for (long a : SEEDS) {
            queue.add(toAddr(a));
        }
        for (long a : EXTRA) {
            queue.add(toAddr(a));
        }

        int dataHops = 0;
        while (!queue.isEmpty() && visited.size() < 4000 && funcs.size() < 400) {
            Address t = queue.poll();
            if (!visited.add(t)) {
                continue;
            }
            ReferenceIterator rit =
                currentProgram.getReferenceManager().getReferencesTo(t);
            for (Reference r : rit) {
                Address from = r.getFromAddress();
                Function f = getFunctionContaining(from);
                if (f != null) {
                    funcs.put(f.getEntryPoint(), f);
                } else {
                    // a data pointer: follow it one hop (bounded)
                    if (visited.size() + queue.size() < 3000) {
                        queue.add(from);
                        dataHops++;
                    }
                }
            }
        }

        PrintWriter out = new PrintWriter(
            "C:\\Users\\Administrator\\ghidra_scripts\\ptr_re_out.txt", "UTF-8");
        out.println("visited=" + visited.size() + " dataHops=" + dataHops
            + " functions=" + funcs.size());
        out.println();

        for (Function f : funcs.values()) {
            out.println("==================================================");
            out.println("FUNCTION " + f.getEntryPoint() + " name=" + f.getName());
            DecompileResults res = ifc.decompileFunction(f, 90, monitor);
            if (res != null && res.decompileCompleted() && res.getDecompiledFunction() != null) {
                out.println(res.getDecompiledFunction().getC());
            } else {
                out.println("  decompile failed");
            }
            out.println("  --- callers:");
            for (Reference r : getReferencesTo(f.getEntryPoint())) {
                Function c = getFunctionContaining(r.getFromAddress());
                out.println("      " + r.getFromAddress() + "  "
                    + (c != null ? c.getName() + "@" + c.getEntryPoint() : "?"));
            }
            out.println();
        }
        out.close();
        ifc.dispose();
        println("PtrRE done: visited=" + visited.size() + " functions=" + funcs.size());
    }
}
