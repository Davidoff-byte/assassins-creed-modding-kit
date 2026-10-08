using System;
using System.IO;
using System.Reflection;
using AnvilToolkit.FileTypes.AnvilNext;
using AnvilToolkit.Utils;

class Program
{
    static readonly string[] SearchDirs =
    {
        AppContext.BaseDirectory,
        @"C:\SteamLibrary\steamapps\common\Assassins Creed\Libs",
        @"C:\SteamLibrary\steamapps\common\Assassins Creed",
        @"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue",
    };

    static Program()
    {
        AppDomain.CurrentDomain.AssemblyResolve += (s, e) =>
        {
            var name = new AssemblyName(e.Name).Name + ".dll";
            foreach (var d in SearchDirs)
            {
                var p = Path.Combine(d, name);
                if (File.Exists(p)) return Assembly.LoadFrom(p);
            }
            return null;
        };
    }

    // Usage: atktool <resource-file> [out.xml]
    static void Main(string[] args)
    {
        var inPath = args[0];
        var outPath = args.Length > 1 ? args[1] : inPath + ".xml";
        try
        {
            var sf = new ScimitarFile(inPath, Game.Rogue);   // ctor deserializes
            var xml = sf.Data?.ToXml();
            if (xml == null) { Console.WriteLine("no xml"); return; }
            File.WriteAllText(outPath, xml.ToString());
            Console.WriteLine($"wrote {outPath} ({new FileInfo(outPath).Length} bytes)");
        }
        catch (Exception ex)
        {
            Console.WriteLine("failed: " + ex.GetType().Name + ": " + ex.Message);
        }
    }
}
