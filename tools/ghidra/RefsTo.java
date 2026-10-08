import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.BufferedReader;
import java.io.FileReader;
import java.io.PrintWriter;

// Usage: RefsTo.java <targetListFile> <outFile>
public class RefsTo extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String listFile = args[0];
        String outFile  = args[1];
        PrintWriter out = new PrintWriter(outFile, "UTF-8");
        BufferedReader br = new BufferedReader(new FileReader(listFile));
        String line;
        while ((line = br.readLine()) != null) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            long t = Long.parseLong(line.replace("0x", "").replace("0X", ""), 16);
            Address a = toAddr(t);
            Function f = getFunctionAt(a);
            out.println("=== REFERENCES TO " + a + " (" + (f != null ? f.getName() : "?") + ")");
            for (Reference r : getReferencesTo(a)) {
                Function c = getFunctionContaining(r.getFromAddress());
                out.println("  from " + r.getFromAddress() + " type=" + r.getReferenceType()
                            + " in " + (c != null ? c.getName() + "@" + c.getEntryPoint() : "?"));
            }
        }
        br.close();
        out.close();
    }
}
