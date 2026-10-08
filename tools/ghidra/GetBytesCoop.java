import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

// Dump the first bytes of the AccCoop M2 hook targets for pattern-scan signatures.
public class GetBytesCoop extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] targets = {
            0x1403664e0L, // Ai::UpdateCamera
            0x140358f00L, // Ai::AdjustCameraAfterPhysics
            0x140107450L, // Ai::AIUpdate
            0x14046b6f0L, // Ai::SpawningManagerUpdate
        };
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bytes_coop.txt", "UTF-8");
        for (long t : targets) {
            Address a = toAddr(t);
            Function f = getFunctionAt(a);
            out.println("=== " + a + " name=" + (f != null ? f.getName() : "?"));
            byte[] b = new byte[40];
            currentProgram.getMemory().getBytes(a, b);
            StringBuilder sb = new StringBuilder();
            for (byte x : b) {
                sb.append(String.format("%02X ", x));
            }
            out.println("BYTES40: " + sb.toString().trim());
        }
        out.close();
    }
}
