import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import java.io.PrintWriter;

public class Action18SP extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_action18.txt", "UTF-8");
        Memory mem = currentProgram.getMemory();

        // pattern 1: FUN_004caa4a with the three E8 immediates wildcarded
        byte[] p1 = {
            (byte)0x55, (byte)0x8B, (byte)0xEC, (byte)0x56, (byte)0x8B, (byte)0x75, (byte)0x14,
            (byte)0x83, (byte)0xEC, (byte)0x10, (byte)0x8D, (byte)0x46, (byte)0x40, (byte)0x8B,
            (byte)0xCC, (byte)0x50, (byte)0xE8, 0, 0, 0, 0,
            (byte)0x83, (byte)0xEC, (byte)0x10, (byte)0x8D, (byte)0x46, (byte)0x30, (byte)0x8B,
            (byte)0xCC, (byte)0x50, (byte)0xE8, 0, 0, 0, 0,
            (byte)0x0F, (byte)0xB6, (byte)0x46, (byte)0x2C, (byte)0x50, (byte)0xFF, (byte)0x76,
            (byte)0x28, (byte)0x8D, (byte)0x46, (byte)0x18, (byte)0x83, (byte)0xEC, (byte)0x10,
            (byte)0x8B, (byte)0xCC, (byte)0x50, (byte)0xE8, 0, 0, 0, 0,
            (byte)0x8B, (byte)0x4D, (byte)0x10, (byte)0xFF, (byte)0x76, (byte)0x14, (byte)0x03,
            (byte)0x4D, (byte)0x08, (byte)0xFF, (byte)0x55, (byte)0x0C, (byte)0x5E, (byte)0x5D,
            (byte)0xC3
        };
        byte[] m1 = new byte[p1.length];
        java.util.Arrays.fill(m1, (byte)0xFF);
        m1[16] = m1[17] = m1[18] = m1[19] = 0;
        m1[30] = m1[31] = m1[32] = m1[33] = 0;
        m1[52] = m1[53] = m1[54] = m1[55] = 0;

        out.println("=== SP search: FUN_004caa4a pattern (3 call targets wildcarded) ===");
        Address addr = toAddr(0x401000L);
        int found = 0;
        while (true) {
            addr = mem.findBytes(addr, p1, m1, true, monitor);
            if (addr == null) { break; }
            Function cfn = getFunctionContaining(addr);
            out.println("  HIT @ " + addr + " in " + cfn);
            found++;
            if (found > 8) { break; }
            addr = addr.add(1);
        }
        out.println("  total: " + found);

        // pattern 2: 12-byte head only (broad)
        byte[] p2 = {
            (byte)0x55, (byte)0x8B, (byte)0xEC, (byte)0x56, (byte)0x8B, (byte)0x75, (byte)0x14,
            (byte)0x83, (byte)0xEC, (byte)0x10, (byte)0x8D, (byte)0x46, (byte)0x40
        };
        out.println("=== SP search: 12-byte head 55 8B EC 56 8B 75 14 83 EC 10 8D 46 40 ===");
        addr = toAddr(0x401000L);
        found = 0;
        while (true) {
            addr = mem.findBytes(addr, p2, null, true, monitor);
            if (addr == null) { break; }
            Function cfn = getFunctionContaining(addr);
            out.println("  HIT @ " + addr + " in " + cfn);
            found++;
            if (found > 20) { break; }
            addr = addr.add(1);
        }
        out.println("  total: " + found);
        out.close();
    }
}
