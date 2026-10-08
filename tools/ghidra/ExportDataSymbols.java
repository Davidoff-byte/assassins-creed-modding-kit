import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.ReferenceManager;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolIterator;
import ghidra.program.model.symbol.SymbolType;
import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;

/**
 * Exports the global-variable map: every labelled data symbol with its referencing functions.
 * This is the "shared state" map - which code touches which global (camera manager, world,
 * managers, vtables' targets, string tables). Useful for the current mod work and any rewrite.
 *
 * Args [0] output path.
 */
public class ExportDataSymbols extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String outPath = args.length > 0 ? args[0]
                : "C:\\Users\\Administrator\\bf4_re\\analysis\\globals.txt";

        FunctionManager fm = currentProgram.getFunctionManager();
        ReferenceManager rm = currentProgram.getReferenceManager();

        List<Symbol> symbols = new ArrayList<>();
        SymbolIterator sit = currentProgram.getSymbolTable().getAllSymbols(true);
        while (sit.hasNext()) {
            Symbol s = sit.next();
            if (s.getSymbolType() != SymbolType.LABEL) {
                continue;
            }
            Address a = s.getAddress();
            if (!a.isMemoryAddress()) {
                continue;
            }
            MemoryBlock b = currentProgram.getMemory().getBlock(a);
            if (b == null || b.isExecute()) {
                continue;
            }
            symbols.add(s);
        }

        int written = 0;
        try (PrintWriter pw = new PrintWriter(new BufferedWriter(new FileWriter(outPath)))) {
            pw.println("# data symbols for " + currentProgram.getName() + " : " + symbols.size());
            for (Symbol s : symbols) {
                Address a = s.getAddress();
                Set<String> refFns = new TreeSet<>();
                ReferenceIterator refs = rm.getReferencesTo(a);
                while (refs.hasNext()) {
                    Reference r = refs.next();
                    Function f = fm.getFunctionContaining(r.getFromAddress());
                    if (f != null) {
                        refFns.add(f.getName());
                    } else {
                        refFns.add(r.getFromAddress().toString());
                    }
                }
                if (refFns.isEmpty()) {
                    continue;
                }
                String name = s.getName(true);
                StringBuilder sb = new StringBuilder();
                sb.append(String.format("%08x", a.getOffset())).append(' ').append(name)
                  .append(" refs=").append(refFns.size()).append(" : ");
                int i = 0;
                for (String fn : refFns) {
                    if (i++ >= 40) {
                        sb.append(",...");
                        break;
                    }
                    sb.append(fn).append(',');
                }
                pw.println(sb);
                written++;
            }
        }
        println("ExportDataSymbols: " + written + " referenced globals -> " + outPath);
    }
}
