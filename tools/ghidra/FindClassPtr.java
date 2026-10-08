// FindClassPtr.java - locate the native class StaticClass functions by following
// string -> struct -> code pointers. For each interesting class-name string we:
//   1. scan initialized data for u32 values that point AT the string (struct fields)
//   2. scan data + code for u32 values / references that point AT those struct fields
//   3. decompile the functions that reference them.
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import java.io.PrintWriter;
import java.util.LinkedHashSet;

public class FindClassPtr extends GhidraScript {

    private static final String[] NEEDLES = {
        "ActivePowerComponent_Blink",
        "ActivePowerComponent",
        "PowersComponent",
        "DisTweaks_Blink",
    };

    private static boolean interesting(String s) {
        for (String n : NEEDLES) if (s.contains(n)) return true;
        return false;
    }

    private long u32(Address a) {
        try { return currentProgram.getMemory().getInt(a) & 0xffffffffL; } catch (Exception e) { return -1; }
    }

    private AddressSet initializedData() {
        AddressSet set = new AddressSet();
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            if (b.isInitialized() && !b.isExecute()) set.add(b.getStart(), b.getEnd());
        }
        return set;
    }

    @Override
    public void run() throws Exception {
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        PrintWriter out = new PrintWriter(
            "C:\\Users\\Administrator\\ghidra_scripts\\class_ptr_out.txt", "UTF-8");

        Listing listing = currentProgram.getListing();
        DataIterator dit = listing.getDefinedData(true);
        LinkedHashSet<Function> funcs = new LinkedHashSet<>();
        AddressSet dataSet = initializedData();

        while (dit.hasNext()) {
            Data d = dit.next();
            Object v;
            try { v = d.getValue(); } catch (Exception e) { continue; }
            if (!(v instanceof String)) continue;
            String s = (String) v;
            if (!interesting(s)) continue;
            long strAddr = d.getAddress().getOffset();

            out.println("### CLASS STRING " + d.getAddress() + " : " + s);

            // 1) scan data for u32 == strAddr (struct fields pointing at the string)
            LinkedHashSet<Long> structFields = new LinkedHashSet<>();
            for (Address a : dataSet.getAddresses(true)) {
                if (u32(a) == strAddr) structFields.add(a.getOffset());
            }
            out.println("    struct fields pointing at string: " + structFields.size());

            // 2) for each struct field, find references TO it (code or data)
            for (Long field : structFields) {
                Address fa = toAddr(field);
                ReferenceIterator rit = currentProgram.getReferenceManager().getReferencesTo(fa);
                for (Reference r : rit) {
                    Address from = r.getFromAddress();
                    Function f = getFunctionContaining(from);
                    out.println("    struct " + fa + " <- REF " + from + "  "
                        + (f != null ? f.getName() + "@" + f.getEntryPoint() : "(data)"));
                    if (f != null) funcs.add(f);
                }
                // also scan data for u32 == field (another hop)
                for (Address a : dataSet.getAddresses(true)) {
                    if (u32(a) == field) {
                        out.println("    struct " + fa + " <- data ptr at " + a);
                    }
                }
            }
        }

        out.println();
        out.println("FUNCTIONS: " + funcs.size());
        for (Function f : funcs) {
            out.println("==================================================");
            out.println("FUNCTION " + f.getEntryPoint() + " name=" + f.getName());
            DecompileResults res = ifc.decompileFunction(f, 120, monitor);
            if (res != null && res.decompileCompleted() && res.getDecompiledFunction() != null) {
                out.println(res.getDecompiledFunction().getC());
            } else {
                out.println("  decompile failed");
            }
            out.println();
        }

        out.close();
        ifc.dispose();
        println("FindClassPtr done: " + funcs.size() + " functions");
    }
}
