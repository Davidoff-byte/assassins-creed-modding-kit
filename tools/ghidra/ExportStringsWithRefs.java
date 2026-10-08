import ghidra.app.script.GhidraScript;
import ghidra.program.model.data.DataType;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.ReferenceManager;
import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.Set;
import java.util.TreeSet;

/**
 * Exports every defined string with its ADDRESS and referencing functions.
 * Addresses are hook anchors for live instrumentation; the ref-functions complement gamedb.
 *
 * Args [0] output path.
 */
public class ExportStringsWithRefs extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String outPath = args.length > 0 ? args[0]
                : "C:\\Users\\Administrator\\bf4_re\\analysis\\strings_ghidra.txt";
        FunctionManager fm = currentProgram.getFunctionManager();
        ReferenceManager rm = currentProgram.getReferenceManager();
        int n = 0;
        try (PrintWriter pw = new PrintWriter(new BufferedWriter(new FileWriter(outPath)))) {
            pw.println("# strings with refs for " + currentProgram.getName()
                    + " (address, text, referencing functions)");
            DataIterator it = currentProgram.getListing().getDefinedData(true);
            while (it.hasNext()) {
                Data d = it.next();
                DataType dt = d.getDataType();
                String tn = dt.getName().toLowerCase();
                if (!tn.contains("string") && !tn.contains("unicode")) {
                    continue;
                }
                Object v = d.getValue();
                if (v == null) {
                    continue;
                }
                String s = v.toString();
                if (s.length() < 4 || s.length() > 300) {
                    continue;
                }
                s = s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t");
                Set<String> fns = new TreeSet<>();
                ReferenceIterator r = rm.getReferencesTo(d.getAddress());
                while (r.hasNext()) {
                    Reference ref = r.next();
                    Function f = fm.getFunctionContaining(ref.getFromAddress());
                    fns.add(f != null ? f.getName() : ref.getFromAddress().toString());
                }
                StringBuilder sb = new StringBuilder();
                sb.append(String.format("%08x", d.getAddress().getOffset())).append(" \"")
                  .append(s).append("\" refs=");
                int i = 0;
                for (String fn : fns) {
                    if (i++ >= 20) {
                        sb.append(",...");
                        break;
                    }
                    sb.append(fn).append(',');
                }
                pw.println(sb);
                n++;
            }
        }
        println("ExportStringsWithRefs: " + n + " strings -> " + outPath);
    }
}
