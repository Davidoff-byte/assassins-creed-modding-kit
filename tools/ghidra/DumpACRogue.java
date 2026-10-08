import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import java.io.BufferedReader;
import java.io.FileReader;
import java.io.PrintWriter;

// Reads acrogue_dump_targets.txt lines "0xADDR len" and dumps hex+ascii to acrogue_dump.txt
public class DumpACRogue extends GhidraScript {
    @Override
    public void run() throws Exception {
        String listFile = "C:\\Users\\Administrator\\ghidra_scripts\\acrogue_dump_targets.txt";
        String outFile  = "C:\\Users\\Administrator\\ghidra_scripts\\acrogue_dump.txt";
        PrintWriter out = new PrintWriter(outFile, "UTF-8");
        BufferedReader br = new BufferedReader(new FileReader(listFile));
        String line;
        while ((line = br.readLine()) != null) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] p = line.split("\\s+");
            long a = Long.parseLong(p[0].replace("0x", "").replace("0X", ""), 16);
            int len = p.length > 1 ? Integer.parseInt(p[1]) : 128;
            Address addr = toAddr(a);
            out.println("=== 0x" + Long.toHexString(a) + " len=" + len + " ===");
            byte[] b = new byte[len];
            try { currentProgram.getMemory().getBytes(addr, b); }
            catch (Exception e) { out.println("  read failed: " + e.getMessage()); continue; }
            for (int i = 0; i < len; i += 16) {
                StringBuilder hex = new StringBuilder();
                StringBuilder asc = new StringBuilder();
                for (int j = i; j < Math.min(i + 16, len); j++) {
                    hex.append(String.format("%02X ", b[j]));
                    int c = b[j] & 0xff;
                    asc.append(c >= 32 && c < 127 ? (char) c : '.');
                }
                out.println(String.format("%08X  %-48s  %s", a + i, hex.toString(), asc.toString()));
            }
        }
        br.close();
        out.close();
    }
}
