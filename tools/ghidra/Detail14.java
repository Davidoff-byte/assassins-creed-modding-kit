import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Detail14 extends GhidraScript {
    Memory mem;
    PrintWriter out;
    long imgBase = 0x400000L, imgEnd = 0x2B00000L;

    void disasm(long from, long to) throws Exception {
        out.println("--- disasm 0x" + Long.toHexString(from) + " .. 0x" + Long.toHexString(to) + " ---");
        Address a = toAddr(from);
        Instruction ins = getInstructionAt(a);
        if (ins == null) { try { disassemble(a); } catch (Exception e) {} ins = getInstructionAt(a); }
        int guard = 0;
        while (ins != null && ins.getAddress().getOffset() < to && guard++ < 200) {
            out.println("  " + ins.getAddress() + "  " + ins.toString());
            ins = ins.getNext();
        }
        out.println();
    }

    String rttiName(long vtAddr) {
        StringBuilder sb = new StringBuilder();
        try {
            Address vt = toAddr(vtAddr);
            int colVal = mem.getInt(vt.subtract(4));
            long col = colVal & 0xFFFFFFFFL;
            sb.append("  vtable-4 = 0x").append(String.format("%08X", colVal)).append("\n");
            if (col < 0x10000 || col > 0x7FFF0000L) return sb.toString();
            int sig = mem.getInt(toAddr(col));
            int td = mem.getInt(toAddr(col + 0xC));
            long tdL = td & 0xFFFFFFFFL;
            sb.append("  COL at 0x").append(Long.toHexString(col)).append(" sig=").append(sig)
              .append(" tdPtr=0x").append(String.format("%08X", td)).append("\n");
            if (tdL > 0x10000 && tdL < 0x7FFF0000L) {
                StringBuilder ns = new StringBuilder();
                for (int i = 0; i < 160; i++) {
                    int b = mem.getByte(toAddr(tdL + 8 + i)) & 0xFF;
                    if (b == 0) break;
                    ns.append((char) b);
                }
                sb.append("  name@td+8: ").append(ns).append("\n");
            }
        } catch (Exception e) {
            sb.append("  (rtti walk failed: ").append(e.getMessage()).append(")\n");
        }
        return sb.toString();
    }

    long findVtStart(long slot) {
        long p = slot;
        for (int guard = 0; guard < 2000; guard++) {
            try {
                int v = mem.getInt(toAddr(p - 4));
                long uv = v & 0xFFFFFFFFL;
                if (uv >= imgBase && uv < imgEnd) p -= 4; else break;
            } catch (Exception e) { break; }
        }
        return p;
    }

    @Override
    public void run() throws Exception {
        mem = currentProgram.getMemory();
        out = new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bfsp_detail14.txt", "UTF-8");

        disasm(0x1128F70L, 0x1128FC0L);
        disasm(0x12398A0L, 0x12398F0L);
        disasm(0x1122150L, 0x1122190L);

        long s1 = findVtStart(0x2697C4CL);
        out.println("=== vtable containing slot 0x2697C4C ===");
        out.println("  start = 0x" + Long.toHexString(s1) + "  slot offset = +0x" + Long.toHexString(0x2697C4CL - s1));
        out.println(rttiName(s1));

        long s2 = findVtStart(0x26A5724L);
        out.println("=== vtable containing slot 0x26A5724 ===");
        out.println("  start = 0x" + Long.toHexString(s2) + "  slot offset = +0x" + Long.toHexString(0x26A5724L - s2));
        out.println(rttiName(s2));

        out.println("=== src vtable 0x2697010 ===");
        out.println(rttiName(0x2697010L));

        out.println("=== references to 0x2697010 (constructor/instantiation) ===");
        for (Reference r : getReferencesTo(toAddr(0x2697010L))) {
            out.println("  from " + r.getFromAddress() + " " + r.getReferenceType() + "  in " + getFunctionContaining(r.getFromAddress()));
        }
        out.println();
        out.close();
    }
}
