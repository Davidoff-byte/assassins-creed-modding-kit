import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

// List callers of a target address: pass the hex address as the first script arg
// (defaults to the camera-manager constructor 0x505be0).
public class CallersOfBFSP extends GhidraScript {
    @Override
    public void run() throws Exception {
        long target = 0x00505be0L;
        String[] args = getScriptArgs();
        if (args.length > 0) {
            target = Long.parseLong(args[0].replace("0x", "").replace("0X", ""), 16);
        }
        Address ad = toAddr(target);
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_callers.txt", "UTF-8");
        out.println("callers of " + Long.toHexString(target));
        int n = 0;
        for (Reference r : getReferencesTo(ad)) {
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
