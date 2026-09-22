using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class Program
{
    [STAThread]
    static void Main()
    {
        string dir = Path.GetDirectoryName(Process.GetCurrentProcess().MainModule.FileName);
        if (string.IsNullOrEmpty(dir))
            dir = Environment.CurrentDirectory;
        Directory.SetCurrentDirectory(dir);
        string ui = Path.Combine(dir, "ui.py");
        if (!File.Exists(ui))
        {
            MessageBox.Show("ui.py missing next to AW_FutaDepot.exe", "AW_FutaDepot");
            return;
        }
        string py = FindPython(dir);
        if (py == null)
        {
            MessageBox.Show("Python 3 with Tcl/Tk is required.\n\nwinget install Python.Python.3.12", "AW_FutaDepot");
            return;
        }
        var psi = new ProcessStartInfo();
        psi.FileName = py;
        string name = Path.GetFileName(py).ToLowerInvariant();
        psi.Arguments = (name == "py.exe" || name == "pyw.exe") ? "-3 \"" + ui + "\"" : "\"" + ui + "\"";
        psi.WorkingDirectory = dir;
        psi.UseShellExecute = false;
        try { Process.Start(psi); }
        catch (Exception ex) { MessageBox.Show(ex.Message, "AW_FutaDepot"); }
    }

    static string FindPython(string dir)
    {
        string[] local = {
            Path.Combine(dir, "runtime", "pythonw.exe"),
            Path.Combine(dir, "python", "pythonw.exe"),
            Path.Combine(dir, "pythonw.exe")
        };
        foreach (string p in local)
            if (File.Exists(p)) return p;
        string[] names = { "pyw.exe", "pythonw.exe", "py.exe", "python.exe" };
        string path = Environment.GetEnvironmentVariable("PATH") ?? "";
        foreach (string name in names)
        {
            foreach (string folder in path.Split(Path.PathSeparator))
            {
                try
                {
                    string cand = Path.Combine(folder.Trim(), name);
                    if (File.Exists(cand)) return cand;
                }
                catch { }
            }
        }
        string la = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string pf = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        string[] roots = {
            Path.Combine(la, "Programs", "Python"),
            Path.Combine(pf, "Python"),
            @"C:\Python312", @"C:\Python311", @"C:\Python310"
        };
        foreach (string root in roots)
        {
            if (!Directory.Exists(root)) continue;
            try
            {
                foreach (string d in Directory.GetDirectories(root))
                {
                    string w = Path.Combine(d, "pythonw.exe");
                    if (File.Exists(w)) return w;
                }
                string w2 = Path.Combine(root, "pythonw.exe");
                if (File.Exists(w2)) return w2;
            }
            catch { }
        }
        return null;
    }
}
