using System;
using System.Runtime.InteropServices;
using System.Threading;

class TestWatch {
    static int[] buf = new int[0x1000];
    static volatile bool stop = false;

    static void Main(string[] args) {
        GCHandle handle = GCHandle.Alloc(buf, GCHandleType.Pinned);
        IntPtr addr = handle.AddrOfPinnedObject();
        Console.WriteLine("WATCH_ADDR=0x" + addr.ToInt32().ToString("X8"));
        Console.Out.Flush();

        for (int t = 0; t < 8; t++) {
            Thread th = new Thread(Worker);
            th.IsBackground = false;
            th.Start(t);
        }

        DateTime end = DateTime.UtcNow.AddSeconds(75);
        while (DateTime.UtcNow < end) {
            Thread.Sleep(250);
        }
        stop = true;
        Thread.Sleep(500);
        Console.WriteLine("CREEP_OK");
        Console.Out.Flush();
    }

    static void Worker(object o) {
        int v = (int)o * 1000000;
        while (!stop) {
            // all threads pound the SAME dword: stresses multi-thread hits
            buf[0] = ++v;
        }
    }
}
