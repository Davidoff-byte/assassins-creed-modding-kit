import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.ReferenceManager;
import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;

/**
 * Exports every vtable-like run of code pointers from initialized non-executable data.
 * For each: start address, slot count, referencing functions (ctor / type-check sites), and
 * each slot's function name. This is the class map for both current work and a future rewrite.
 *
 * Args [0] output path; [1] min slots (default 3).
 */
public class ExportVtables extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String outPath = args.length > 0 ? args[0]
                : "C:\\Users\\Administrator\\bf4_re\\analysis\\vtables.txt";
        int minSlots = args.length > 1 ? Integer.parseInt(args[1]) : 3;

        Memory mem = currentProgram.getMemory();
        FunctionManager fm = currentProgram.getFunctionManager();
        ReferenceManager rm = currentProgram.getReferenceManager();
        long imageBase = currentProgram.getImageBase().getOffset();
        long imageEnd = imageBase + 0x5000000L;

        List<long[]> vtables = new ArrayList<>();

        for (MemoryBlock block : mem.getBlocks()) {
            if (!block.isInitialized() || block.isExecute()) {
                continue;
            }
            long start = block.getStart().getOffset();
            long end = block.getEnd().getOffset();
            long runStart = -1;
            int runLen = 0;
            for (long addr = start; addr + 4 <= end; addr += 4) {
                boolean isCodePtr = false;
                try {
                    int v = mem.getInt(toAddr(addr));
                    long uv = v & 0xFFFFFFFFL;
                    if (uv >= imageBase && uv < imageEnd) {
                        if (fm.getFunctionAt(toAddr(uv)) != null) {
                            isCodePtr = true;
                        }
                    }
                } catch (Exception e) {
                    // unreadable - treat as terminator
                }
                if (isCodePtr) {
                    if (runStart < 0) {
                        runStart = addr;
                        runLen = 0;
                    }
                    runLen++;
                } else {
                    if (runStart >= 0 && runLen >= minSlots) {
                        vtables.add(new long[] { runStart, runLen });
                    }
                    runStart = -1;
                    runLen = 0;
                }
            }
            if (runStart >= 0 && runLen >= minSlots) {
                vtables.add(new long[] { runStart, runLen });
            }
        }

        try (PrintWriter pw = new PrintWriter(new BufferedWriter(new FileWriter(outPath)))) {
            pw.println("# vtable export for " + currentProgram.getName() + " : " + vtables.size()
                    + " vtables (min slots " + minSlots + ")");
            for (long[] v : vtables) {
                long va = v[0];
                int n = (int) v[1];
                Set<String> refFns = new TreeSet<>();
                ReferenceIterator refs = rm.getReferencesTo(toAddr(va));
                while (refs.hasNext()) {
                    Reference r = refs.next();
                    Address from = r.getFromAddress();
                    Function f = fm.getFunctionContaining(from);
                    refFns.add(f != null ? f.getName() : from.toString());
                }
                pw.println(String.format("VT %08x slots=%d refs=%s", va, n, String.join(",", refFns)));
                for (int i = 0; i < n; i++) {
                    int fv;
                    try {
                        fv = mem.getInt(toAddr(va + i * 4));
                    } catch (Exception e) {
                        break;
                    }
                    long uv = fv & 0xFFFFFFFFL;
                    Function f = fm.getFunctionAt(toAddr(uv));
                    pw.println(String.format("  [%02d] %08x %s", i, uv, f != null ? f.getName() : "?"));
                }
            }
        }
        println("ExportVtables: " + vtables.size() + " vtables -> " + outPath);
    }
}
