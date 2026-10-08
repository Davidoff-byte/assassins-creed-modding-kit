// BlinkComponent.java - find the Blink/Powers component classes (StaticClass
// constructors) and decompile them. Uses substring match like BlinkRE.java.
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import java.io.PrintWriter;
import java.util.LinkedHashSet;

public class BlinkComponent extends GhidraScript {

    private static final String[] NEEDLES = {
        "ActivePowerComponent_Blink",
        "ActivePowerComponent",
        "PowersComponent",
        "DisTweaks_Blink",
        "BlinkShowRange",
    };

    private static boolean interesting(String s) {
        for (String n : NEEDLES) if (s.contains(n)) return true;
        return false;
    }

    @Override
    public void run() throws Exception {
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter(
            "C:\\Users\\Administrator\\ghidra_scripts\\blink_component_out.txt", "UTF-8");

        Listing listing = currentProgram.getListing();
        DataIterator dit = listing.getDefinedData(true);
        LinkedHashSet<Function> funcs = new LinkedHashSet<>();
        int matched = 0;

        while (dit.hasNext()) {
            Data d = dit.next();
            Object v;
            try { v = d.getValue(); } catch (Exception e) { continue; }
            if (!(v instanceof String)) continue;
            String s = (String) v;
            if (!interesting(s)) continue;
            matched++;
            out.println("### STRING " + d.getAddress() + " : " + s);
            ReferenceIterator rit = currentProgram.getReferenceManager().getReferencesTo(d.getAddress());
            for (Reference r : rit) {
                Address from = r.getFromAddress();
                Function f = getFunctionContaining(from);
                out.println("    REF from " + from + "  "
                    + (f != null ? f.getName() + "@" + f.getEntryPoint() : "(data)"));
                if (f != null) funcs.add(f);
            }
        }

        out.println();
        out.println("TOTAL matched: " + matched + " strings, " + funcs.size() + " functions");
        out.println();

        for (Function f : funcs) {
            out.println("==================================================");
            out.println("FUNCTION " + f.getEntryPoint() + " name=" + f.getName());
            DecompileResults res = ifc.decompileFunction(f, 120, monitor);
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
        println("BlinkComponent done: " + matched + " strings, " + funcs.size() + " functions");
    }
}
