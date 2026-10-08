import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class DumpAll extends GhidraScript {
    @Override
    public void run() throws Exception {
        // 1) all functions
        PrintWriter fn = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\acc_functions.txt", "UTF-8");
        FunctionIterator fit = currentProgram.getFunctionManager().getFunctions(true);
        int fc = 0;
        while (fit.hasNext()) {
            Function f = fit.next();
            fn.println(f.getEntryPoint() + "\t" + f.getBody().getNumAddresses() + "\t" + f.getName());
            fc++;
        }
        fn.println("TOTAL_FUNCTIONS " + fc);
        fn.close();

        // 2) all defined strings + referencing functions
        PrintWriter st = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\acc_strings.txt", "UTF-8");
        PrintWriter xr = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\acc_string_refs.txt", "UTF-8");
        Listing listing = currentProgram.getListing();
        DataIterator it = listing.getDefinedData(true);
        int sc = 0;
        while (it.hasNext()) {
            Data d = it.next();
            Object v;
            try {
                v = d.getValue();
            } catch (Exception e) {
                continue;
            }
            if (!(v instanceof String)) {
                continue;
            }
            String s = ((String) v).replace("\n", " ").replace("\r", " ").replace("\t", " ");
            if (s.length() < 3) {
                continue;
            }
            st.println(d.getAddress() + "\t" + s);
            sc++;
            for (Reference r : getReferencesTo(d.getAddress())) {
                Address from = r.getFromAddress();
                Function f = getFunctionContaining(from);
                String who = (f != null) ? (f.getEntryPoint() + " " + f.getName()) : ("code " + from);
                xr.println(who + "\t" + d.getAddress() + "\t" + s);
            }
        }
        st.println("TOTAL_STRINGS " + sc);
        st.close();
        xr.close();
    }
}
