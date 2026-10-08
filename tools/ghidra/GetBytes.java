import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import java.io.PrintWriter;

public class GetBytes extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] targets = {0x1420f3d20L, 0x1414a6270L};
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bytes_out.txt", "UTF-8");
        for (long t : targets) {
            Address a = toAddr(t);
            Function f = getFunctionAt(a);
            out.println("=== " + a + " name=" + (f != null ? f.getName() : "?"));
            if (f == null) {
                continue;
            }
            byte[] b = new byte[32];
            currentProgram.getMemory().getBytes(a, b);
            StringBuilder sb = new StringBuilder();
            for (byte x : b) {
                sb.append(String.format("%02X ", x));
            }
            out.println("BYTES32: " + sb.toString().trim());
            InstructionIterator it = currentProgram.getListing().getInstructions(f.getBody(), true);
            while (it.hasNext()) {
                Instruction ins = it.next();
                String m = ins.getMnemonicString();
                if (m.equalsIgnoreCase("RET") || m.startsWith("RET")) {
                    out.println("  RET at " + ins.getAddress() + " : " + ins.toString());
                }
            }
        }
        out.close();
    }
}
