import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import java.io.BufferedReader;
import java.io.FileReader;
import java.io.PrintWriter;

// Dumps the first N bytes of each target function as a hex string (for hook signatures).
public class BytesACRogue extends GhidraScript {
    @Override
    public void run() throws Exception {
        String listFile = "C:\\Users\\Administrator\\ghidra_scripts\\acrogue_targets.txt";
        String outFile  = "C:\\Users\\Administrator\\ghidra_scripts\\acrogue_bytes.txt";
        PrintWriter out = new PrintWriter(outFile, "UTF-8");
        BufferedReader br = new BufferedReader(new FileReader(listFile));
        String line;
        while ((line = br.readLine()) != null) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            long t = Long.parseLong(line.replace("0x", "").replace("0X", ""), 16);
            Address a = toAddr(t);
            Function f = getFunctionAt(a);
            byte[] b = new byte[32];
            try { currentProgram.getMemory().getBytes(a, b); }
            catch (Exception e) { out.println(String.format("0x%X  READFAIL", t)); continue; }
            StringBuilder sb = new StringBuilder();
            for (byte x : b) sb.append(String.format("%02X ", x));
            out.println(String.format("0x%X  %s  %s", t, sb.toString().trim(),
                                      f != null ? f.getName() : "?"));
        }
        br.close();
        out.close();
    }
}
