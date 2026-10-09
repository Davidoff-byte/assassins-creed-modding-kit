using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using AnvilToolkit.FileTypes.AnvilNext;
using AnvilToolkit.Utils;

class Program
{
    static readonly string AtkDir = @"D:\ac4work\tools\AnvilToolkit";

    static Program()
    {
        AppDomain.CurrentDomain.AssemblyResolve += (s, e) =>
        {
            var name = new AssemblyName(e.Name).Name + ".dll";
            foreach (var d in new[] { AppContext.BaseDirectory, AtkDir, Path.Combine(AtkDir, "Libs") })
            {
                var p = Path.Combine(d, name);
                if (File.Exists(p)) return Assembly.LoadFrom(p);
            }
            return null;
        };
    }

    static void InitAtk(Game g)
    {
        // Mirror MainWindow ctor preconditions needed for headless deserialization.
        Directory.SetCurrentDirectory(AtkDir); // ATK loads Libs/*.dll and Lists/*.gfl by relative path
        Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);
        var ci = System.Globalization.CultureInfo.InvariantCulture;
        System.Globalization.CultureInfo.DefaultThreadCurrentCulture = ci;
        System.Globalization.CultureInfo.DefaultThreadCurrentUICulture = ci;
        DataStorage.DirectXTexPath = Path.Combine(AtkDir, "Libs\\DirectXTexNetImpl.dll");
        DataStorage.ToolVersion = "1.3.6";
        DataStorage.ElapsedTime = (uint)DateTime.UtcNow.Subtract(new DateTime(1970, 1, 1)).TotalSeconds;
        DataStorage.TempPath = Path.Combine(Path.GetTempPath(), "AnvilToolkit");
        Directory.CreateDirectory(DataStorage.TempPath);
        DataStorage.GlobalScimitarClassReader = new ScimitarClassReader();
        DataStorage.ActiveGame = g; // selects Lists/<Game>.gfl for FileReference name resolution
        try { HashedData.CheckStrings(); } catch (Exception ex) { Console.WriteLine("CheckStrings: " + ex.Message); }
        try
        {
            GameFileList.CheckStrings(); // async load; wait for it
            var waited = 0;
            var last = -1; var stable = 0;
            while (waited < 60000)
            {
                var n = GameFileList.List == null ? -1 : GameFileList.List.Count;
                if (n >= 0 && n == last) { if (++stable >= 8) break; } else stable = 0;
                last = n;
                System.Threading.Thread.Sleep(100); waited += 100;
            }
            Console.WriteLine("  file list: " + (GameFileList.List != null ? GameFileList.List.Count + " entries" : "NOT LOADED"));
        }
        catch (Exception ex) { Console.WriteLine("GameFileList: " + ex.Message); }
    }

    static void Main(string[] args)
    {
        if (args.Length == 0) { Console.WriteLine("usage: atkbf hash <hex...> | dump <file> [out.xml] [--game G]"); return; }

        if (args[0] == "hash")
        {
            InitAtk(Game.BlackFlag);
            foreach (var a in args.Skip(1))
            {
                try
                {
                    var h = Convert.ToUInt32(a.Replace("0x", ""), 16);
                    string name = "?";
                    try { var n = h.GetHashedString(); if (n != null) name = n; } catch (Exception ex) { name = "ex:" + ex.Message; }
                    var t = ScimitarClassRegistry.GetType(h);
                    Console.WriteLine($"0x{h:X8}: exists={ScimitarClassRegistry.Exists(h)} type={(t?.FullName ?? "null")} name={name}");
                }
                catch (Exception ex) { Console.WriteLine(a + ": EX " + ex.GetType().Name + ": " + ex.Message); }
            }
            return;
        }

        if (args[0] == "dump")
        {
            InitAtk(Game.BlackFlag);
            var path = args[1];
            var outXml = args.Length > 2 && !args[2].StartsWith("--") ? args[2] : path + ".xml";
            var gameName = "BlackFlag";
            for (int i = 0; i < args.Length - 1; i++) if (args[i] == "--game") gameName = args[i + 1];
            var g = (Game)Enum.Parse(typeof(Game), gameName, true);

            Console.WriteLine("== " + Path.GetFileName(path) + " game=" + g);
            ScimitarFile sf;
            try { sf = new ScimitarFile(path, g); }
            catch (Exception ex) { Console.WriteLine("  ctor EX: " + ex.GetType().Name + ": " + ex.Message); return; }

            var data = sf.Data;
            if (data == null) { Console.WriteLine("  Data NULL"); return; }
            string name = "?";
            try { var n = data.Hash.GetHashedString(); if (n != null) name = n; } catch { }
            var t = ScimitarClassRegistry.GetType(data.Hash);
            Console.WriteLine($"  class={data.GetType().FullName} Failed={data.Failed} Hash=0x{data.Hash:X8} name={name} registryType={(t?.FullName ?? "null")}");
            if (t == null) { Console.WriteLine("  -> not XML-supported"); return; }

            try
            {
                // call WriteXml directly so the real exception surfaces
                var t2 = data.GetType();
                var mi = t2.GetMethod("WriteXml");
                if (mi == null) { Console.WriteLine("  no WriteXml method"); return; }
                object xmlObj = null;
                try { xmlObj = mi.Invoke(data, new object[] { null }); }
                catch (TargetInvocationException tie)
                {
                    Console.WriteLine("  WriteXml EX: " + (tie.InnerException ?? tie).GetType().Name + ": " + (tie.InnerException ?? tie).Message);
                    Console.WriteLine((tie.InnerException ?? tie).StackTrace);
                    return;
                }
                var xml = xmlObj as System.Xml.Linq.XElement;
                if (xml == null) { Console.WriteLine("  WriteXml returned null"); return; }
                File.WriteAllText(outXml, xml.ToString());
                Console.WriteLine("  wrote " + outXml + " (" + new FileInfo(outXml).Length + " B)");
            }
            catch (Exception ex) { Console.WriteLine("  ToXml EX: " + ex.GetType().Name + ": " + ex.Message); }
            return;
        }

        if (args[0] == "compile")
        {
            var inXml = args[1];
            var outBin = args[2];
            var gameName = "BlackFlag";
            for (int i = 0; i < args.Length - 1; i++) if (args[i] == "--game") gameName = args[i + 1];
            InitAtk((Game)Enum.Parse(typeof(Game), gameName, true));
            var ok = AnvilToolkit.Utils.XmlUtils.CompileXml(inXml, outBin);
            Console.WriteLine("compile " + (ok ? "OK" : "FAILED") + " -> " + outBin + " (" + (File.Exists(outBin) ? new FileInfo(outBin).Length + " B" : "no file") + ")");
            return;
        }

        if (args[0] == "resolve")
        {
            // atkbf resolve <keyHex> [blockHex] [--game G]
            var gameName = "BlackFlag";
            for (int i = 0; i < args.Length - 1; i++) if (args[i] == "--game") gameName = args[i + 1];
            InitAtk((Game)Enum.Parse(typeof(Game), gameName, true));
            if (GameFileList.List == null) { Console.WriteLine("file list not loaded"); return; }
            Console.WriteLine("list entries: " + GameFileList.List.Count);
            var key = Convert.ToUInt32(args[1].Replace("0x", ""), 16);
            var blk = args.Length > 2 && !args[2].StartsWith("--") ? Convert.ToUInt32(args[2].Replace("0x", ""), 16) : 0;
            var variants = new (string, ulong)[]
            {
                ("key|block<<32", (ulong)key | ((ulong)blk << 32)),
                ("block|key<<32", (ulong)blk | ((ulong)key << 32)),
                ("key", key),
                ("key|1<<32", (ulong)key | 0x100000000UL),
            };
            foreach (var (label, v) in variants)
            {
                var path = GameFileList.GetFileReference(v);
                var isGlobal = "";
                Console.WriteLine($"  {label}: 0x{v:X16} -> {path}");
            }
            return;
        }

        if (args[0] == "resolve64")
        {
            // atkbf resolve64 <hexU64...> [--game G] -> GameFileList.GetFileReference(ulong)
            var gameName = "BlackFlag";
            for (int i = 0; i < args.Length - 1; i++) if (args[i] == "--game") gameName = args[i + 1];
            InitAtk((Game)Enum.Parse(typeof(Game), gameName, true));
            if (GameFileList.List == null) { Console.WriteLine("file list not loaded"); return; }
            Console.WriteLine("list entries: " + GameFileList.List.Count);
            foreach (var a in args.Skip(1))
            {
                if (a.StartsWith("--")) break;
                ulong v;
                try { v = Convert.ToUInt64(a.Replace("0x", ""), 16); }
                catch (Exception ex) { Console.WriteLine(a + ": parse EX " + ex.Message); continue; }
                string path;
                try { path = GameFileList.GetFileReference(v); }
                catch (Exception ex) { path = "EX:" + ex.Message; }
                Console.WriteLine($"0x{v:X16} -> {path}");
            }
            return;
        }

        if (args[0] == "classname")
        {
            // atkbf classname <hexU32...> [--game G] -> reverse-lookup a Scimitar class hash
            var gameName = "BlackFlag";
            for (int i = 0; i < args.Length - 1; i++) if (args[i] == "--game") gameName = args[i + 1];
            InitAtk((Game)Enum.Parse(typeof(Game), gameName, true));
            foreach (var a in args.Skip(1))
            {
                if (a.StartsWith("--")) break;
                uint h;
                try { h = Convert.ToUInt32(a.Replace("0x", ""), 16); }
                catch (Exception ex) { Console.WriteLine(a + ": parse EX " + ex.Message); continue; }
                string nm = "?";
                try { var n = h.GetHashedString(); if (n != null) nm = n; } catch { }
                var t = ScimitarClassRegistry.GetType(h);
                Console.WriteLine($"0x{h:X8}: exists={ScimitarClassRegistry.Exists(h)} type={(t?.FullName ?? "null")} name={nm}");
            }
            return;
        }

        if (args[0] == "list")
        {
            // atkbf list <substr> [--game G] -> search the file list for names
            var gameName = "BlackFlag";
            for (int i = 0; i < args.Length - 1; i++) if (args[i] == "--game") gameName = args[i + 1];
            InitAtk((Game)Enum.Parse(typeof(Game), gameName, true));
            if (GameFileList.List == null) { Console.WriteLine("file list not loaded"); return; }
            var sub = args[1].ToLower();
            var snapshot = new List<KeyValuePair<ulong, GameFileListEntry>>();
            lock (GameFileList.List) { } // no-op to document intent
            foreach (var kv in GameFileList.List.ToArray()) snapshot.Add(kv);
            var shown = 0;
            foreach (var kv in snapshot)
            {
                var path = "/";
                try { path = GameFileList.GetFileReference(kv.Key); } catch { }
                if (path.ToLower().Contains(sub))
                {
                    Console.WriteLine($"0x{kv.Key:X16} {path}");
                    if (++shown >= 60) break;
                }
            }
            Console.WriteLine("shown: " + shown);
            return;
        }

        Console.WriteLine("unknown mode");
    }
}
