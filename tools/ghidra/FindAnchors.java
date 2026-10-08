// Find native AI anchor strings in Dishonored.exe and decompile the functions that reference them.
// Run: analyzeHeadless <proj> Dishonored -process Dishonored.exe -noanalysis -postScript FindAnchors.java <outdir> -scriptPath <dir>

import java.io.File;
import java.io.FileWriter;
import java.util.*;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.util.task.ConsoleTaskMonitor;

public class FindAnchors extends GhidraScript {
    private static final String[] ANCHORS = {
        "OnAISetSenses", "OnOverrideAwarenessDisplay", "DisThreatPerceptionComponent",
        "m_Threats", "m_fEngagedThreatRadius", "m_fUnawareThreatRadius",
        "DisAttention", "ThreatTerminatedCallback", "Awareness", "DisBehavior",
        "OnAISetSensesInternal", "SetSenses", "AttentionTarget"
    };

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        File outdir = new File(args.length > 0 ? args[0] : "anchors");
        outdir.mkdirs();

        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        ConsoleTaskMonitor mon = new ConsoleTaskMonitor();

        Set<Function> funcs = new LinkedHashSet<>();
        StringBuilder report = new StringBuilder();

        DataIterator it = currentProgram.getListing().getDefinedData(true);
        while (it.hasNext()) {
            Data d = it.next();
            if (!d.hasStringValue()) continue;
            String val = String.valueOf(d.getValue());
            for (String a : ANCHORS) {
                if (val.contains(a)) {
                    report.append(String.format("STRING %s  \"%s\"%n", d.getAddress(), val));
                    for (Reference r : getReferencesTo(d.getAddress())) {
                        Address from = r.getFromAddress();
                        Function f = getFunctionContaining(from);
                        report.append(String.format("   ref from %s  func=%s%n", from,
                                f != null ? (f.getEntryPoint() + " " + f.getName()) : "?"));
                        if (f != null) funcs.add(f);
                    }
                }
            }
        }

        report.append(String.format("%n=== %d functions referenced%n", funcs.size()));
        Function cur = null;
        for (Function f : funcs) {
            try {
                DecompileResults res = dec.decompileFunction(f, 90, mon);
                if (res != null && res.decompileCompleted() && res.getDecompiledFunction() != null) {
                    FileWriter w = new FileWriter(new File(outdir, f.getEntryPoint() + "_" + f.getName() + ".c"));
                    w.write(res.getDecompiledFunction().getC());
                    w.close();
                    report.append("  wrote ").append(f.getEntryPoint()).append(" ").append(f.getName()).append("\n");
                }
            } catch (Exception e) {
                report.append("  fail ").append(f.getEntryPoint()).append(" ").append(e).append("\n");
            }
        }

        FileWriter w = new FileWriter(new File(outdir, "_anchors.txt"));
        w.write(report.toString());
        w.close();
        println(report.toString());
    }
}
