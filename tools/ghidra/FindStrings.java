import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class FindStrings extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] needles = {
            "Crouch", "Stalk", "Counter", "Parry", "WeaponType", "1Hand",
            "DualWield", "Vanish", "ActionBlockCrouching", "RestrictCrouching",
            "PlayerStalking", "HideSpot", "StealthPose", "Toggle Player Vanish",
            "ActivityCrouch"
        };
        Listing listing = currentProgram.getListing();
        DataIterator it = listing.getDefinedData(true);
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\strings_out.txt", "UTF-8");
        int count = 0;
        while (it.hasNext()) {
            Data d = it.next();
            Object v;
            try {
                v = d.getValue();
            } catch (Exception e) {
                continue;
            }
            if (!(v instanceof String)) {
                continue;
            }
            String s = (String) v;
            if (s.startsWith("g_") || s.contains("HorizonTexture") || s.contains("LODBlend")) {
                continue;
            }
            for (String n : needles) {
                if (s.contains(n)) {
                    Reference[] refs = getReferencesTo(d.getAddress());
                    StringBuilder sb = new StringBuilder();
                    for (Reference r : refs) {
                        Address from = r.getFromAddress();
                        Function f = getFunctionContaining(from);
                        if (f != null) {
                            sb.append(f.getName()).append("@").append(f.getEntryPoint()).append(";");
                        } else {
                            sb.append("code@").append(from).append(";");
                        }
                    }
                    out.println("STR\t" + d.getAddress() + "\t" + s.replace("\n", " ").replace("\t", " ") + "\tREFS\t" + sb);
                    count++;
                    break;
                }
            }
        }
        out.println("TOTAL_MATCHES " + count);
        out.close();
    }
}
