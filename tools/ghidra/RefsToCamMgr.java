import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

// Find all references to the BF SP camera-manager global 0x02abe588.
public class RefsToCamMgr extends GhidraScript {
    @Override
    public void run() throws Exception {
        long target = 0x02abe588L;
        Address ad = toAddr(target);
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_cammgr_refs.txt", "UTF-8");
        int n = 0;
        Reference[] refs = getReferencesTo(ad);
        for (Reference r : refs) {
            Address from = r.getFromAddress();
            Function f = getFunctionContaining(from);
            String who = (f != null) ? (f.getEntryPoint() + " " + f.getName()) : ("code " + from);
            out.println(who + "\t" + from + "\t" + r.getReferenceType());
            n++;
        }
        out.println("TOTAL " + n);
        out.close();
    }
}
