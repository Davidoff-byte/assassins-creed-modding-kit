import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;
public class GetBytesCoop2 extends GhidraScript {
  public void run() throws Exception {
    long[] t={0x1401a7a40L,0x1400f6a70L};
    PrintWriter o=new PrintWriter("C:\\Users\\Administrator\\ghidra_scripts\\bytes_coop2.txt","UTF-8");
    for(long x:t){ Address a=toAddr(x); Function f=getFunctionAt(a); o.println("=== "+a+" "+(f!=null?f.getName():"?"));
      byte[] b=new byte[24]; currentProgram.getMemory().getBytes(a,b); StringBuilder s=new StringBuilder();
      for(byte c:b) s.append(String.format("%02X ",c)); o.println("BYTES24: "+s.toString().trim()); }
    o.close(); } }
