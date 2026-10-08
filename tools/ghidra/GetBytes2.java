import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import java.io.PrintWriter;
public class GetBytes2 extends GhidraScript {
  public void run() throws Exception {
    long[] t={0x141807200L,0x1418041f0L};
    PrintWriter o=new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bytes2_out.txt","UTF-8");
    for(long x:t){ Address a=toAddr(x); Function f=getFunctionAt(a); o.println("=== "+a+" "+(f!=null?f.getName():"?"));
      byte[] b=new byte[32]; currentProgram.getMemory().getBytes(a,b); StringBuilder s=new StringBuilder();
      for(byte c:b) s.append(String.format("%02X ",c)); o.println("BYTES32: "+s.toString().trim());
      InstructionIterator it=currentProgram.getListing().getInstructions(f.getBody(),true); int n=0;
      while(it.hasNext()&&n<6){ Instruction ins=it.next(); o.println("  "+ins.getAddress()+" : "+ins.toString()); n++; } }
    o.close(); } }
