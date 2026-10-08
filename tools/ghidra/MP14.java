import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;
import java.util.*;

public class MP14 extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfmp_skin14.txt", "UTF-8");
        Map<String, Long> wanted = new LinkedHashMap<>();
        wanted.put("CharacterSkinsComponent", 0L);
        wanted.put("ActionSwapSkin", 0L);
        wanted.put("MissionActionSwapSkin", 0L);
        wanted.put("PLAYER_SKIN", 0L);
        wanted.put("SwapSkin", 0L);
        wanted.put("CharacterSkinInventoryItem", 0L);
        wanted.put("CharacterSkinsDLCElement", 0L);
        wanted.put("PlayerCharacterData", 0L);
        wanted.put("D2M_RequestSwapSkin", 0L);
        wanted.put("M2All_SwapSkinEventWithId", 0L);
        wanted.put("C2S_Skin_WantToSelectSkin", 0L);

        int count = 0;
        out.println("=== skin-ish strings ===");
        DataIterator it = currentProgram.getListing().getDefinedData(true);
        while (it.hasNext() && count < 4000) {
            Data d = it.next();
            Object v = d.getValue();
            if (!(v instanceof String)) continue;
            String s = (String) v;
            if (s.indexOf("kin") < 0 && s.indexOf("KIN") < 0) continue;
            count++;
            if (count <= 80) out.println("  " + d.getAddress() + "  " + s);
            for (Map.Entry<String, Long> e : wanted.entrySet()) {
                if (e.getValue() == 0L && s.equals(e.getKey())) e.setValue(d.getAddress().getOffset());
            }
        }
        out.println("(skin-ish string count: " + count + ")");
        out.println();

        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        int decompCount = 0;
        for (Map.Entry<String, Long> e : wanted.entrySet()) {
            out.println("=== \"" + e.getKey() + "\" @ " + (e.getValue() == 0 ? "NOT FOUND" : "0x" + Long.toHexString(e.getValue())) + " ===");
            if (e.getValue() == 0L) { out.println(); continue; }
            int n = 0;
            for (Reference r : getReferencesTo(toAddr(e.getValue()))) {
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("  " + r.getFromAddress() + " " + r.getReferenceType() + "  in " + cf);
                if (cf != null && n < 2 && decompCount < 6) {
                    n++; decompCount++;
                    DecompileResults dr = ifc.decompileFunction(cf, 120, monitor);
                    if (dr.getDecompiledFunction() != null) {
                        String c = dr.getDecompiledFunction().getC();
                        if (c.length() > 3500) c = c.substring(0, 3500) + "\n...(truncated)";
                        out.println("--- fn " + cf.getEntryPoint() + " ---");
                        out.println(c);
                    }
                }
            }
            out.println();
        }
        out.close();
    }
}
