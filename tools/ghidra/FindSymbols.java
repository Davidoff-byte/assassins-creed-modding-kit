// FindSymbols.java - list every symbol / function whose name contains one of
// the interesting substrings. Reveals RTTI-derived vtable and class names.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolIterator;
import java.io.PrintWriter;

public class FindSymbols extends GhidraScript {
    private static final String[] NEEDLES = { "Blink", "ActivePower", "PowersComponent", "PowerComponent" };

    private static boolean hit(String s) {
        for (String n : NEEDLES) {
            if (s.contains(n)) {
                return true;
            }
        }
        return false;
    }

    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter(
            "C:\\Users\\Administrator\\ghidra_scripts\\symbols_out.txt", "UTF-8");

        out.println("================ SYMBOLS ================");
        SymbolIterator sit = currentProgram.getSymbolTable().getAllSymbols(true);
        int ns = 0;
        while (sit.hasNext()) {
            Symbol s = sit.next();
            if (hit(s.getName())) {
                out.println(s.getAddress() + "  " + s.getName()
                    + "  [" + s.getSymbolType() + "]");
                ns++;
            }
        }

        out.println();
        out.println("================ FUNCTIONS ================");
        FunctionIterator fit = currentProgram.getFunctionManager().getFunctions(true);
        int nf = 0;
        while (fit.hasNext()) {
            Function f = fit.next();
            if (hit(f.getName())) {
                out.println(f.getEntryPoint() + "  " + f.getName()
                    + "  (params=" + f.getParameterCount() + ")");
                nf++;
            }
        }
        out.println();
        out.println("symbols=" + ns + " functions=" + nf);
        out.close();
        println("FindSymbols done: " + ns + " symbols, " + nf + " functions");
    }
}
