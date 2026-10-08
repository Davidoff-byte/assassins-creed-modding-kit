import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import java.io.PrintWriter;

public class DumpInstr extends GhidraScript {
    @Override
    public void run() throws Exception {
        long start = 0x0063ba70L;
        int count = 70;
        Listing listing = currentProgram.getListing();
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_instr.txt", "UTF-8");
        Address ad = toAddr(start);
        Instruction ins = listing.getInstructionAt(ad);
        for (int i = 0; i < count && ins != null; i++) {
            out.println(ins.getAddress() + "  " + ins.toString());
            ins = ins.getNext();
        }
        out.close();
    }
}
