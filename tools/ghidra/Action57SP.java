import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolTable;
import java.io.PrintWriter;

public class Action57SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action57.txt", "UTF-8");
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        SymbolTable st = currentProgram.getSymbolTable();
        for (String name : new String[] { "main", "_main", "wmain", "WinMain", "mainCRTStartup" }) {
            for (Symbol s : st.getSymbols(name)) {
                out.println("=== symbol " + name + " @" + s.getAddress() + " ===");
                Function cf = getFunctionAt(s.getAddress());
                if (cf != null) {
                    DecompileResults dr = ifc.decompileFunction(cf, 120, monitor);
                    if (dr.getDecompiledFunction() != null) {
                        String c = dr.getDecompiledFunction().getC();
                        if (c.length() > 5000) { c = c.substring(0, 5000) + "\n...(truncated)"; }
                        out.println(c);
                    }
                }
                out.println();
            }
        }
        out.close();
    }
}
